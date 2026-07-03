"""Bazys backend entrypoint."""

from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

from app.database import engine, Base
from app.models import Assessment
from app.routers.assessments import router as assessments_router

app = FastAPI(
    title="Bazys - Execution Intelligence Platform",
    description="Execution layer for operational reality reconstruction.",
    version="0.1.0",
)

templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(assessments_router)

Base.metadata.create_all(bind=engine)


@app.get("/")
def read_root():
    return {"status": "ok", "platform": "Bazys", "version": "0.1.0"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.get("/assessment/{token}", response_class=HTMLResponse)
def assessment_page(request: Request, token: str):
    """Render applicant-facing assessment form."""
    from app.database import SessionLocal
    db = SessionLocal()
    assessment = db.query(Assessment).filter(Assessment.token == token).first()
    db.close()
    return templates.TemplateResponse("assessment.html", {
        "request": request,
        "token": token,
        "assessment_id": assessment.id if assessment else None,
    })
