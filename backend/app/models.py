"""
Bazys Core Models - execution-oriented ontology.

Designed to eventually be shared across all domains
(construction, manufacturing, logistics, healthcare, etc.).
"""

import enum
from datetime import datetime, date
from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean, Enum,
    DateTime, Date, JSON, ForeignKey
)
from sqlalchemy.orm import relationship
from app.database import Base


# ─── Enums ───────────────────────────────────────────────────────────────────

class CountryTier(str, enum.Enum):
    KNOCKOUT = "knockout"     # rejected immediately
    LOW = "low"               # low priority
    MEDIUM = "medium"         # neutral
    HIGH = "high"             # preferred
    UNKNOWN = "unknown"


class ApplicationStatus(str, enum.Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    SCREENED = "screened"
    REJECTED = "rejected"
    ADVANCED = "advanced"
    HIRED = "hired"


class EvaluationDecision(str, enum.Enum):
    KNOCKOUT = "knockout"
    REJECT = "reject"
    REVIEW = "review"
    ADVANCE = "advance"


class DocumentStatus(str, enum.Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    IMPLEMENTED = "implemented"
    STABLE = "stable"
    DEPRECATED = "deprecated"


# ─── Entity Base ─────────────────────────────────────────────────────────────

class EntityMixin:
    """Base entity with identity — every Bazys entity inherits this."""
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


# ─── Assessment (Recruitment) Domain ─────────────────────────────────────────

class CountryProfile(Base):
    """Country tier classification for recruitment."""
    __tablename__ = "country_profiles"

    id = Column(Integer, primary_key=True, index=True)
    country_name = Column(String(100), unique=True, nullable=False)
    tier = Column(Enum(CountryTier), default=CountryTier.UNKNOWN, nullable=False)
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class AssessmentTemplate(Base):
    """A structured questionnaire template (e.g., 'GDI Recruitment').
    Maps to Bazys ontology: Object (document/module/service)."""
    __tablename__ = "assessment_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, default="")
    version = Column(String(20), default="0.1.0")
    status = Column(Enum(DocumentStatus), default=DocumentStatus.DRAFT)
    config = Column(JSON, default=dict)  # scoring rules, weights
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    questions = relationship("Question", back_populates="template", cascade="all, delete-orphan", order_by="Question.order")
    assessments = relationship("Assessment", back_populates="template")


class Question(Base):
    """A single question in an assessment template.
    Properties: knockout, severity, weight — per Bazys Rule ontology."""
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(Integer, ForeignKey("assessment_templates.id"), nullable=False)
    order = Column(Integer, nullable=False)
    key = Column(String(100), nullable=False)         # e.g. "country", "age", "english_level"
    label = Column(String(500), nullable=False)        # the question text
    question_type = Column(String(50), default="text") # text, select, boolean, date, file
    options = Column(JSON, default=list)               # for select/multi-select
    required = Column(Boolean, default=True)

    # Bazys Rule ontology: knockout, severity (impact), weight (importance)
    is_knockout = Column(Boolean, default=False)
    severity = Column(Float, default=1.0)              # how impactful (0.0 - 1.0)
    weight = Column(Float, default=1.0)                # scoring weight
    rule_logic = Column(Text, default="")              # optional JS/Python expression

    description = Column(Text, default="")             # help text

    template = relationship("AssessmentTemplate", back_populates="questions")
    answers = relationship("Answer", back_populates="question", cascade="all, delete-orphan")


class Applicant(Base):
    """A person applying (worker/applicant).
    Maps to Bazys ontology: Actor (entity with identity & role)."""
    __tablename__ = "applicants"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(300), nullable=False)
    email = Column(String(200), default="")
    phone = Column(String(50), default="")
    country = Column(String(100), default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    assessments = relationship("Assessment", back_populates="applicant")


class Assessment(Base):
    """A completed assessment session.
    Maps to Bazys ontology: Process (event-driven state evolution)."""
    __tablename__ = "assessments"

    id = Column(Integer, primary_key=True, index=True)
    applicant_id = Column(Integer, ForeignKey("applicants.id"), nullable=False)
    template_id = Column(Integer, ForeignKey("assessment_templates.id"), nullable=False)
    status = Column(Enum(ApplicationStatus), default=ApplicationStatus.DRAFT)
    token = Column(String(64), unique=True, index=True)  # unique link for applicant
    total_score = Column(Float, default=0.0)
    decision = Column(Enum(EvaluationDecision), default=None, nullable=True)
    decision_reason = Column(Text, default="")
    summary = Column(Text, default="")                   # AI-generated summary (future)

    # Metadata
    ip_address = Column(String(50), default="")
    user_agent = Column(String(500), default="")
    started_at = Column(DateTime, nullable=True)
    submitted_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    applicant = relationship("Applicant", back_populates="assessments")
    template = relationship("AssessmentTemplate", back_populates="assessments")
    answers = relationship("Answer", back_populates="assessment", cascade="all, delete-orphan")
    events = relationship("AssessmentEvent", back_populates="assessment", cascade="all, delete-orphan")


class Answer(Base):
    """A single answer to a question in an assessment.
    Maps to Bazys ontology: Event (something happened in execution)."""
    __tablename__ = "answers"

    id = Column(Integer, primary_key=True, index=True)
    assessment_id = Column(Integer, ForeignKey("assessments.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    value = Column(Text, default="")      # the raw answer
    score = Column(Float, default=0.0)    # calculated score for this answer
    notes = Column(Text, default="")      # evaluator notes

    assessment = relationship("Assessment", back_populates="answers")
    question = relationship("Question", back_populates="answers")


class AssessmentEvent(Base):
    """Audit trail of state changes — reconstructable reality.
    Maps to Bazys ontology: Event + State (state evolves through events)."""
    __tablename__ = "assessment_events"

    id = Column(Integer, primary_key=True, index=True)
    assessment_id = Column(Integer, ForeignKey("assessments.id"), nullable=False)
    event_type = Column(String(50), nullable=False)   # created, submitted, evaluated, knocked-out, advanced
    actor = Column(String(100), default="system")
    payload = Column(JSON, default=dict)               # event-specific data
    previous_state = Column(String(50), default="")
    new_state = Column(String(50), default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    assessment = relationship("Assessment", back_populates="events")


# ─── Bazys Core Ontology (future) ──────────────────────────────────────────

class Entity(Base):
    """
    Core Bazys entity — foundation for all domain entities.
    Will be extended as more domains come online.
    """
    __tablename__ = "entities"

    id = Column(Integer, primary_key=True, index=True)
    entity_type = Column(String(100), nullable=False)   # polymorphic: worker, resource, material, etc.
    name = Column(String(300), nullable=False)
    attributes = Column(JSON, default=dict)
    status = Column(String(50), default="active")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
