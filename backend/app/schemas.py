from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime


# ─── Assessment Template ──────────────────────────────────────────────────

class QuestionCreate(BaseModel):
    key: str
    label: str
    question_type: str = "text"
    options: list[str] = []
    required: bool = True
    order: int = 0
    is_knockout: bool = False
    severity: float = 1.0
    weight: float = 1.0
    rule_logic: str = ""
    description: str = ""


class TemplateCreate(BaseModel):
    name: str
    description: str = ""
    questions: list[QuestionCreate] = []


class TemplateOut(BaseModel):
    id: int
    name: str
    description: str
    version: str
    questions: list[QuestionCreate] = []

    class Config:
        from_attributes = True


# ─── Applicant / Answer ───────────────────────────────────────────────────

class AnswerSubmit(BaseModel):
    question_id: int
    value: str


class AssessmentStart(BaseModel):
    full_name: str
    email: str = ""
    phone: str = ""
    country: str = ""


class AssessmentSubmit(BaseModel):
    answers: list[AnswerSubmit]


class AnswerOut(BaseModel):
    question_id: int
    question_key: str
    question_label: str
    value: str
    score: float

    class Config:
        from_attributes = True


class AssessmentResult(BaseModel):
    id: int
    token: str
    status: str
    decision: Optional[str] = None
    decision_reason: str = ""
    total_score: float
    summary: str = ""

    class Config:
        from_attributes = True


class AssessmentOut(AssessmentResult):
    applicant_name: str = ""
    applicant_country: str = ""
    answers: list[AnswerOut] = []
    events: list[dict] = []


# ─── Admin / Dashboard ────────────────────────────────────────────────────

class AssessmentList(BaseModel):
    id: int
    applicant_name: str
    applicant_country: str
    status: str
    decision: Optional[str] = None
    total_score: float
    created_at: datetime

    class Config:
        from_attributes = True
