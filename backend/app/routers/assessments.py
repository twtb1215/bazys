"""Assessment API endpoints."""

import secrets
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.database import get_db
from app.models import (
    Assessment, Applicant, Answer, Question,
    AssessmentTemplate, ApplicationStatus,
)
from app.schemas import (
    AssessmentStart, AssessmentSubmit, AnswerSubmit,
    AssessmentResult, AssessmentOut, AssessmentList,
    TemplateCreate,
)
from app.services.evaluation import evaluate_assessment

router = APIRouter(prefix="/api/v1")
templates = Jinja2Templates(directory="app/templates")


# ─── Templates ────────────────────────────────────────────────────────────

@router.post("/templates")
def create_template(data: TemplateCreate, db: Session = Depends(get_db)):
    """Create a new assessment template with questions."""
    template = AssessmentTemplate(name=data.name, description=data.description)
    db.add(template)
    db.flush()

    for i, q in enumerate(data.questions):
        question = Question(
            template_id=template.id,
            order=q.order or i + 1,
            key=q.key,
            label=q.label,
            question_type=q.question_type,
            options=q.options,
            required=q.required,
            is_knockout=q.is_knockout,
            severity=q.severity,
            weight=q.weight,
            rule_logic=q.rule_logic,
            description=q.description,
        )
        db.add(question)

    db.commit()
    db.refresh(template)
    return {"id": template.id, "name": template.name}


@router.get("/templates")
def list_templates(db: Session = Depends(get_db)):
    templates = db.query(AssessmentTemplate).all()
    return [
        {"id": t.id, "name": t.name, "questions_count": len(t.questions)}
        for t in templates
    ]


@router.get("/templates/{template_id}")
def get_template(template_id: int, db: Session = Depends(get_db)):
    t = db.query(AssessmentTemplate).filter(AssessmentTemplate.id == template_id).first()
    if not t:
        raise HTTPException(404, "Template not found")
    return {
        "id": t.id,
        "name": t.name,
        "description": t.description,
        "questions": [
            {
                "id": q.id,
                "order": q.order,
                "key": q.key,
                "label": q.label,
                "question_type": q.question_type,
                "options": q.options,
                "required": q.required,
                "is_knockout": q.is_knockout,
                "severity": q.severity,
                "weight": q.weight,
            }
            for q in sorted(t.questions, key=lambda x: x.order)
        ],
    }


# ─── Assessment Flow ──────────────────────────────────────────────────────

@router.post("/assessments/start/{template_id}")
def start_assessment(template_id: int, data: AssessmentStart, db: Session = Depends(get_db)):
    """Create a new assessment and return a unique link."""
    template = db.query(AssessmentTemplate).filter(AssessmentTemplate.id == template_id).first()
    if not template:
        raise HTTPException(404, "Template not found")

    applicant = Applicant(
        full_name=data.full_name,
        email=data.email,
        phone=data.phone,
        country=data.country,
    )
    db.add(applicant)
    db.flush()

    token = secrets.token_urlsafe(32)
    assessment = Assessment(
        applicant_id=applicant.id,
        template_id=template_id,
        token=token,
        status=ApplicationStatus.DRAFT,
    )
    db.add(assessment)
    db.commit()
    db.refresh(assessment)

    return {
        "assessment_id": assessment.id,
        "token": token,
        "link": f"/assessment/{token}",
    }


@router.get("/api/v1/assessments/by-token/{token}")
def get_assessment_by_token(token: str, db: Session = Depends(get_db)):
    """Get assessment questions by token (for the applicant form)."""
    assessment = db.query(Assessment).filter(Assessment.token == token).first()
    if not assessment:
        raise HTTPException(404, "Assessment not found")

    template = assessment.template
    questions = [
        {
            "id": q.id,
            "order": q.order,
            "key": q.key,
            "label": q.label,
            "question_type": q.question_type,
            "options": q.options,
            "required": q.required,
            "description": q.description,
        }
        for q in sorted(template.questions, key=lambda x: x.order)
    ]
    return {
        "assessment_id": assessment.id,
        "applicant_name": assessment.applicant.full_name,
        "questions": questions,
    }


@router.post("/api/v1/assessments/{assessment_id}/submit")
def submit_assessment(assessment_id: int, data: AssessmentSubmit, db: Session = Depends(get_db)):
    """Submit answers and trigger evaluation."""
    assessment = db.query(Assessment).filter(Assessment.id == assessment_id).first()
    if not assessment:
        raise HTTPException(404, "Assessment not found")

    if assessment.status not in (ApplicationStatus.DRAFT, ApplicationStatus.SUBMITTED):
        raise HTTPException(400, f"Assessment already {assessment.status.value}")

    # Save answers
    for ans in data.answers:
        answer = Answer(
            assessment_id=assessment_id,
            question_id=ans.question_id,
            value=ans.value,
        )
        db.add(answer)

    assessment.status = ApplicationStatus.SUBMITTED
    db.commit()

    # Run evaluation
    evaluate_assessment(assessment_id, db)

    db.refresh(assessment)
    return {
        "decision": assessment.decision.value if assessment.decision else "unknown",
        "decision_reason": assessment.decision_reason,
        "total_score": assessment.total_score,
    }


# ─── Manager Dashboard ────────────────────────────────────────────────────

@router.get("/assessments")
def list_assessments(
    status: str = None,
    decision: str = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """List all assessments (manager view)."""
    query = db.query(Assessment)

    if status:
        query = query.filter(Assessment.status == status)
    if decision:
        query = query.filter(Assessment.decision == decision)

    assessments = query.order_by(Assessment.created_at.desc()).limit(limit).all()

    return [
        AssessmentList(
            id=a.id,
            applicant_name=a.applicant.full_name,
            applicant_country=a.applicant.country,
            status=a.status.value,
            decision=a.decision.value if a.decision else None,
            total_score=a.total_score,
            created_at=a.created_at,
        )
        for a in assessments
    ]


@router.get("/assessments/{assessment_id}")
def get_assessment_detail(assessment_id: int, db: Session = Depends(get_db)):
    """Full assessment detail for manager review."""
    a = db.query(Assessment).filter(Assessment.id == assessment_id).first()
    if not a:
        raise HTTPException(404, "Assessment not found")

    return AssessmentOut(
        id=a.id,
        token=a.token,
        status=a.status.value,
        decision=a.decision.value if a.decision else None,
        decision_reason=a.decision_reason,
        total_score=a.total_score,
        summary=a.summary,
        applicant_name=a.applicant.full_name,
        applicant_country=a.applicant.country,
        answers=[
            {
                "question_id": ans.question_id,
                "question_key": ans.question.key,
                "question_label": ans.question.label,
                "value": ans.value,
                "score": ans.score,
            }
            for ans in a.answers
        ],
        events=[
            {
                "event_type": e.event_type,
                "actor": e.actor,
                "payload": e.payload,
                "created_at": e.created_at.isoformat(),
            }
            for e in a.events
        ],
    )
