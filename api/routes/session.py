"""
Session routes — the core tutor loop over HTTP.
State is held server-side in a dict keyed by session_id (UUID).
Each session tracks: domain, current question, conversation history.
Answers are persisted to Supabase after each submission.
"""

import uuid
import asyncio
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.tutor import (
    generate_question,
    format_question_message,
    evaluate_answer,
    evaluate_explanation,
    generate_explain_back_prompt,
    chat_followup,
)
from bot.conversation import DOMAINS
from api.supabase_client import store_answer

router = APIRouter()

# In-memory session store: { session_id: session_dict }
_sessions: dict[str, dict] = {}


# ── Request / Response models ─────────────────────────────────────────────────

class StartRequest(BaseModel):
    domain: str
    user_id: Optional[str] = None


class StartResponse(BaseModel):
    session_id: str
    question_text: str
    domain: str


class AnswerRequest(BaseModel):
    session_id: str
    answer: str


class AnswerResponse(BaseModel):
    is_correct: bool
    feedback: str
    explain_prompt: str


class ExplainRequest(BaseModel):
    session_id: str
    explanation: str


class ExplainResponse(BaseModel):
    feedback: str
    next_question_text: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_session(session_id: str) -> dict:
    s = _sessions.get(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    return s


def _make_session(domain: str, user_id: Optional[str]) -> dict:
    return {
        "domain": domain,
        "user_id": user_id,
        "current_question": None,
        "pending_answer": None,   # holds answer until explanation is submitted
        "conversation_history": [],
        "recent_topics": [],
        "chat_count": 0,
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/domains")
def list_domains():
    return {"domains": DOMAINS}


@router.post("/start", response_model=StartResponse)
def start_session(req: StartRequest):
    if req.domain not in DOMAINS:
        raise HTTPException(status_code=400, detail=f"Unknown domain: {req.domain}")

    session_id = str(uuid.uuid4())
    session = _make_session(req.domain, req.user_id)
    question = generate_question(req.domain, session["recent_topics"])
    session["current_question"] = question
    _sessions[session_id] = session

    return StartResponse(
        session_id=session_id,
        question_text=format_question_message(question),
        domain=req.domain,
    )


@router.post("/answer", response_model=AnswerResponse)
def submit_answer(req: AnswerRequest):
    session = _get_session(req.session_id)
    question = session["current_question"]
    if not question:
        raise HTTPException(status_code=400, detail="No active question")

    feedback, is_correct = evaluate_answer(
        question,
        req.answer,
        session["conversation_history"],
    )

    session["conversation_history"].append({"role": "user", "content": req.answer})
    session["conversation_history"].append({"role": "assistant", "content": feedback})
    if len(session["conversation_history"]) > 12:
        session["conversation_history"] = session["conversation_history"][-12:]

    # Store answer for later — we save to Supabase after explanation (or skip)
    session["pending_answer"] = {
        "answer": req.answer,
        "is_correct": is_correct,
    }

    if is_correct:
        explain_prompt = generate_explain_back_prompt(question["topic"])
    else:
        correct_letter = question["answer"]
        correct_text = question["options"].get(correct_letter, "")
        explain_prompt = (
            f"The correct answer was {correct_letter}) {correct_text}. "
            f"In your own words, can you explain why that's the right choice?"
        )

    return AnswerResponse(
        is_correct=is_correct,
        feedback=feedback,
        explain_prompt=explain_prompt,
    )


@router.post("/explain", response_model=ExplainResponse)
async def submit_explanation(req: ExplainRequest):
    session = _get_session(req.session_id)
    question = session["current_question"]
    if not question:
        raise HTTPException(status_code=400, detail="No active question")

    feedback = evaluate_explanation(question, req.explanation)

    session["conversation_history"].append({"role": "user", "content": req.explanation})
    session["conversation_history"].append({"role": "assistant", "content": feedback})

    if question["topic"] not in session["recent_topics"]:
        session["recent_topics"].append(question["topic"])
    session["recent_topics"] = session["recent_topics"][-10:]

    # Persist answer to Supabase
    pending = session.pop("pending_answer", None)
    if pending and session.get("user_id"):
        await store_answer(
            user_id=session["user_id"],
            domain=session["domain"],
            topic=question["topic"],
            question_text=question["question"],
            correct_answer=question["answer"],
            user_answer=pending["answer"],
            is_correct=pending["is_correct"],
        )

    next_q = generate_question(session["domain"], session["recent_topics"])
    session["current_question"] = next_q
    session["chat_count"] = 0

    return ExplainResponse(
        feedback=feedback,
        next_question_text=format_question_message(next_q),
    )


CHAT_LIMIT = 2

@router.post("/chat")
async def chat(req: AnswerRequest):
    """Free-form follow-up chat within the current session."""
    session = _get_session(req.session_id)
    if session["chat_count"] >= CHAT_LIMIT:
        raise HTTPException(status_code=429, detail="Chat limit reached for this question")
    response = chat_followup(req.answer, session["conversation_history"], session["domain"])
    session["conversation_history"].append({"role": "user", "content": req.answer})
    session["conversation_history"].append({"role": "assistant", "content": response})
    if len(session["conversation_history"]) > 12:
        session["conversation_history"] = session["conversation_history"][-12:]
    session["chat_count"] += 1
    return {"response": response}


@router.post("/skip")
async def skip_explanation(session_id: str):
    session = _get_session(session_id)
    question = session["current_question"]

    if question and question["topic"] not in session["recent_topics"]:
        session["recent_topics"].append(question["topic"])
    session["recent_topics"] = session["recent_topics"][-10:]

    # Persist answer to Supabase even if they skipped the explanation
    pending = session.pop("pending_answer", None)
    if pending and session.get("user_id") and question:
        await store_answer(
            user_id=session["user_id"],
            domain=session["domain"],
            topic=question["topic"],
            question_text=question["question"],
            correct_answer=question["answer"],
            user_answer=pending["answer"],
            is_correct=pending["is_correct"],
        )

    next_q = generate_question(session["domain"], session["recent_topics"])
    session["current_question"] = next_q
    session["chat_count"] = 0

    return {"next_question_text": format_question_message(next_q)}
