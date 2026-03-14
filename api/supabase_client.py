"""
Supabase client for the Python backend.
Uses service_role key — bypasses Row Level Security, so only use server-side.
"""

import os
from supabase import create_client, Client

_client: Client | None = None


def get_supabase() -> Client:
    global _client
    if _client is None:
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
        _client = create_client(url, key)
    return _client


async def store_answer(
    user_id: str,
    domain: str,
    topic: str,
    question_text: str,
    correct_answer: str,
    user_answer: str,
    is_correct: bool,
):
    """Insert one answer row into Supabase."""
    sb = get_supabase()
    sb.table("answers").insert({
        "user_id": user_id,
        "domain": domain,
        "topic": topic,
        "question_text": question_text,
        "correct_answer": correct_answer,
        "user_answer": user_answer,
        "is_correct": is_correct,
    }).execute()


async def fetch_stats(user_id: str) -> list[dict]:
    """Return per-domain accuracy for this user."""
    sb = get_supabase()
    # Supabase doesn't support GROUP BY directly via the client,
    # so we fetch all answers and aggregate in Python.
    res = sb.table("answers").select("domain, is_correct").eq("user_id", user_id).execute()
    rows = res.data or []

    domain_totals: dict[str, dict] = {}
    for row in rows:
        d = row["domain"]
        if d not in domain_totals:
            domain_totals[d] = {"domain": d, "total": 0, "correct": 0}
        domain_totals[d]["total"] += 1
        if row["is_correct"]:
            domain_totals[d]["correct"] += 1

    return list(domain_totals.values())
