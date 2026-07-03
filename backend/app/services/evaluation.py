"""
Bazys Evaluation Engine — the core decision-making service.

Knockout rules are applied first (immediate reject).
Surviving candidates are scored and ranked using weighted criteria.

This implements the Bazys ontology:
  Rule → Action → Event → State transition
"""

from typing import Optional
from sqlalchemy.orm import Session

from app.models import (
    Assessment, Applicant, Answer, AssessmentEvent, Question,
    ApplicationStatus, EvaluationDecision, CountryTier, CountryProfile,
)

# ─── Country Knockout Rules ───────────────────────────────────────────────

# Countries whose applicants are immediately rejected
KNOCKOUT_COUNTRIES = {
    "north korea",
    "nicaragua",
}

# Note: Руслан will add more countries for different tiers later.
# LOW_TIER, HIGH_TIER maps will be added as needed.


# ─── Evaluation Rules ─────────────────────────────────────────────────────

def check_knockout_rules(applicant: Applicant, answers: list[Answer], db: Session) -> Optional[str]:
    """
    Returns a reason string if a knockout rule is triggered, None otherwise.
    Order matters: first knockout wins.
    """
    # 1. Country knockout
    country_lower = (applicant.country or "").strip().lower()

    # Check from CountryProfile table
    profile = db.query(CountryProfile).filter(
        CountryProfile.country_name.ilike(country_lower)
    ).first()
    if profile and profile.tier == CountryTier.KNOCKOUT:
        return f"Country '{applicant.country}' is not eligible (tier: knockout)"

    # Also check hardcoded list
    if country_lower in KNOCKOUT_COUNTRIES:
        return f"Country '{applicant.country}' is not eligible"

    # 2. Passport check
    for a in answers:
        q = db.query(Question).filter(Question.id == a.question_id).first()
        if not q:
            continue
        k = q.key.lower()

        # If no valid passport → knockout
        if k == "passport_valid" and a.value.strip().lower() in ("no", "false", "0", ""):
            return "No valid international passport"

    return None  # all clear


def calculate_score(applicant: Applicant, answers: list[Answer], db: Session) -> float:
    """
    Calculate weighted score for a candidate who passed knockout.
    Returns score in range [0, 100].
    """
    total_weight = 0.0
    weighted_sum = 0.0

    for a in answers:
        q = db.query(Question).filter(Question.id == a.question_id).first()
        if not q or q.is_knockout:
            continue

        weight = q.weight
        total_weight += weight

        score = _score_answer(q, a)
        weighted_sum += weight * score

    if total_weight == 0:
        return 0.0

    return round((weighted_sum / total_weight) * 100, 1)


def _score_answer(question: Question, answer: Answer) -> float:
    """Score a single answer on [0, 1]."""
    val = (answer.value or "").strip().lower()
    key = question.key.lower()

    # Experience scoring
    if key == "years_experience":
        try:
            years = float(val)
            if years >= 10:
                return 1.0
            elif years >= 5:
                return 0.8
            elif years >= 3:
                return 0.6
            elif years >= 1:
                return 0.4
            else:
                return 0.1
        except ValueError:
            return 0.5

    # English level
    if key in ("english_level", "english"):
        english_scores = {
            "native": 1.0, "c2": 1.0, "c1": 0.9,
            "b2": 0.7, "b1": 0.5, "a2": 0.3, "a1": 0.1,
            "yes": 0.6, "no": 0.0,
        }
        return english_scores.get(val, 0.3)

    # Technical drawings
    if key == "technical_drawings":
        return 1.0 if val in ("yes", "true", "y", "1") else 0.3

    # Worked abroad
    if key == "worked_abroad":
        return 1.0 if val in ("yes", "true", "y", "1") else 0.4

    # Visa readiness / financial readiness
    if key in ("financial_readiness", "can_afford_costs"):
        return 1.0 if val in ("yes", "true", "y", "1") else 0.0

    # Independence
    if key == "work_independently":
        return 1.0 if val in ("independently", "both", "yes") else 0.5

    # Can record video / send photos
    if key in ("can_record_video", "can_send_photos"):
        return 1.0 if val in ("yes", "true", "y", "1") else 0.2

    # Default: binary yes/no
    if val in ("yes", "true", "y", "1"):
        return 1.0
    elif val in ("no", "false", "n", "0"):
        return 0.0

    return 0.5


def evaluate_assessment(assessment_id: int, db: Session) -> Assessment:
    """Run full evaluation pipeline for an assessment."""
    assessment = db.query(Assessment).filter(Assessment.id == assessment_id).first()
    if not assessment:
        raise ValueError(f"Assessment {assessment_id} not found")

    applicant = assessment.applicant
    answers = assessment.answers

    # Step 1: Knockout check
    knockout_reason = check_knockout_rules(applicant, answers, db)
    if knockout_reason:
        assessment.decision = EvaluationDecision.KNOCKOUT
        assessment.decision_reason = knockout_reason
        assessment.status = ApplicationStatus.REJECTED
        _record_event(assessment, "knocked-out", {"reason": knockout_reason}, db)
        db.commit()
        return assessment

    # Step 2: Calculate score
    score = calculate_score(applicant, answers, db)
    assessment.total_score = score

    # Step 3: Decision based on score
    if score >= 70:
        assessment.decision = EvaluationDecision.ADVANCE
        assessment.status = ApplicationStatus.ADVANCED
        assessment.decision_reason = f"Strong candidate (score: {score})"
    elif score >= 40:
        assessment.decision = EvaluationDecision.REVIEW
        assessment.status = ApplicationStatus.SCREENED
        assessment.decision_reason = f"Needs manual review (score: {score})"
    else:
        assessment.decision = EvaluationDecision.REJECT
        assessment.status = ApplicationStatus.REJECTED
        assessment.decision_reason = f"Below threshold (score: {score})"

    _record_event(assessment, "evaluated", {"score": score, "decision": assessment.decision.value}, db)
    db.commit()
    return assessment


def _record_event(assessment: Assessment, event_type: str, payload: dict, db: Session):
    """Record a state transition event (Bazys Event ontology)."""
    event = AssessmentEvent(
        assessment_id=assessment.id,
        event_type=event_type,
        actor="system",
        payload=payload,
        previous_state=assessment.status.value if assessment.status else "draft",
        new_state=assessment.status.value if assessment.status else "unknown",
    )
    db.add(event)
