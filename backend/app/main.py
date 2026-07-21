"""Bazys backend entrypoint."""

import os
import json
from datetime import datetime
from typing import Any

import httpx
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse

from app.database import engine, Base, get_db
from app.models import Assessment
from app.routers.assessments import router as assessments_router
from sqlalchemy.orm import Session  # type: ignore


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
FILLOUT_SECRET = os.getenv("FILLOUT_SECRET", "")

ANALYSIS_PROMPT = """
Ти — HR-аналітик для GDI (Green Dot International).
Кандидат на роботу в Польщі через GDI.

Дані кандидата з анкети:
{data}

Проаналізуй і дай менеджеру відповідь українською мовою, що включає:
1. Кратка характеристика кандидата (3-4 речення)
2. Його сильні сторони
3. Потенційні ризики (що перевірити)
4. Рекомендація: РЕКОМЕНДОВАНО / ПОТРЕБУЄ ПЕРЕВІРКИ / ВІДМОВА
5. Коротке обґрунтування

Відповідь ОБОВ'ЯЗКОВО як JSON:
{{"summary": "...", "strengths": ["...", "..."], "risks": ["...", "..."], "recommendation": "...", "reasoning": "..."}}
"""

VALID_RECOMMENDATIONS = {"РЕКОМЕНДОВАНО", "ПОТРЕБУЄ ПЕРЕВІРКИ", "ВІДМОВА"}


def extract_candidate_data(body: dict) -> dict:
    if isinstance(body, dict):
        if "data" in body and isinstance(body["data"], dict):
            return body["data"]
        if "answers" in body and isinstance(body["answers"], list):
            return {item.get("label") or item.get("key", ""): item.get("value", "") for item in body["answers"]}
        return body
    return {"raw": str(body)}


async def analyze_with_openai(data: dict) -> dict:
    if not OPENAI_API_KEY:
        return {
            "summary": "AI-аналіз тимчасово недоступний (відсутній ключ OpenAI).",
            "strengths": [],
            "risks": ["Конфігурація: відсутній OPENAI_API_KEY."],
            "recommendation": "ПОТРЕБУЄ ПЕРЕВІРКИ",
            "reasoning": "Автоматичний аналіз вимкнено.",
            "score": None,
            "next_action": "Перевірте конфігурацію сервісу.",
        }

    prompt = ANALYSIS_PROMPT.format(data=json.dumps(data, ensure_ascii=False, default=str))
    async with httpx.AsyncClient(timeout=httpx.Timeout(40.0)) as client:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "response_format": {"type": "json_object"},
            },
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        parsed = json.loads(content)

    recommendation = str(parsed.get("recommendation", "")).upper().strip()
    if recommendation not in VALID_RECOMMENDATIONS:
        recommendation = "ПОТРЕБУЄ ПЕРЕВІРКИ"
    parsed["recommendation"] = recommendation
    parsed.setdefault("score", None)
    parsed.setdefault("next_action", "")
    return parsed


async def route_fillout_result(analysis: dict, candidate_data: dict, db: Session) -> None:
    submission_id = str(
        candidate_data.get("submissionId")
        or candidate_data.get("submission_id")
        or candidate_data.get("id")
        or ""
    )
    row = {
        "Fillout Submission ID": submission_id,
        "AI Decision": analysis.get("recommendation", ""),
        "AI Score": analysis.get("score") if isinstance(analysis.get("score"), (int, float)) else "",
        "AI Summary": analysis.get("summary", ""),
        "AI Next Action": analysis.get("next_action", ""),
        "Recruiter Status": "New",
        "Submitted At": datetime.utcnow().isoformat(),
        "Raw Payload": json.dumps(candidate_data, ensure_ascii=False, default=str),
    }
    print("ZITE_ROW_QUEUE=" + json.dumps(row, ensure_ascii=False, default=str))


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


@app.post("/webhook/fillout-gdi")
async def fillout_gdi_webhook(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid json"}, status_code=400)

    candidate_data = extract_candidate_data(body)
    try:
        analysis = await analyze_with_openai(candidate_data)
    except Exception as e:
        return JSONResponse({"error": f"openai failed: {e}"}, status_code=500)

    db_gen = get_db()
    db: Session = next(db_gen)
    try:
        await route_fillout_result(analysis=analysis, candidate_data=candidate_data, db=db)
    except Exception as e:
        print(f"ROUTING_ERROR={e}")
    finally:
        db.close()

    return JSONResponse({"status": "ok", "recommendation": analysis.get("recommendation")})


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
