"""
FastAPI backend for the AZ-900 Tutor web product.
Run: python run.py   (or uvicorn api.main:app --reload)
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from api.routes import session, progress

load_dotenv()

app = FastAPI(title="AZ-900 Tutor API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(session.router, prefix="/session", tags=["session"])
app.include_router(progress.router, prefix="/progress", tags=["progress"])


@app.get("/health")
def health():
    return {"status": "ok"}
