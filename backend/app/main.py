"""Bazys backend entrypoint."""

from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi import Request

from app.config import settings
from app.database import engine, Base
from app.routers import assessments

app = FastAPI(
    title="Bazys - Execution Intelligence Platform",
    description="Execution layer for operational reality reconstruction.",
    version="0.1.0",
)

templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(assessments.router)

Base.metadata.create_all(bind=engine)

@app.get("/")
def read_root():
    return {"status": "ok", "platform": "Bazys", "version": "0.1.0"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}
