"""
Progress routes — per-user readiness score from Supabase.
"""

from fastapi import APIRouter
from core.scorer import compute_readiness
from api.supabase_client import fetch_stats

router = APIRouter()


@router.get("/{user_id}")
async def get_progress(user_id: str):
    stats = await fetch_stats(user_id)
    overall, breakdown = compute_readiness(stats)
    return {
        "overall": overall,
        "breakdown": breakdown,
        "stats": stats,
    }
