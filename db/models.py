"""Data access layer — all DB queries live here."""

import aiosqlite
from db.database import get_db


# ---------- Users ----------

async def upsert_user(telegram_id: int, username: str):
    async with get_db() as db:
        await db.execute(
            """INSERT INTO users (telegram_id, username)
               VALUES (?, ?)
               ON CONFLICT(telegram_id) DO UPDATE SET username=excluded.username""",
            (telegram_id, username),
        )
        await db.commit()


async def get_user(telegram_id: int) -> dict | None:
    async with get_db() as db:
        async with db.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def set_user_domain(telegram_id: int, domain: str):
    async with get_db() as db:
        await db.execute(
            "UPDATE users SET current_domain = ? WHERE telegram_id = ?",
            (domain, telegram_id),
        )
        await db.commit()


# ---------- Sessions ----------

async def start_session(telegram_id: int, domain: str) -> int:
    async with get_db() as db:
        cur = await db.execute(
            "INSERT INTO sessions (telegram_id, domain) VALUES (?, ?)",
            (telegram_id, domain),
        )
        await db.commit()
        return cur.lastrowid


async def end_session(session_id: int):
    async with get_db() as db:
        await db.execute(
            "UPDATE sessions SET ended_at = datetime('now') WHERE id = ?",
            (session_id,),
        )
        await db.commit()


# ---------- Answers ----------

async def record_answer(
    telegram_id: int,
    session_id: int,
    domain: str,
    topic: str,
    question_text: str,
    correct_answer: str,
    user_answer: str,
    is_correct: bool,
):
    async with get_db() as db:
        await db.execute(
            """INSERT INTO answers
               (telegram_id, session_id, domain, topic, question_text,
                correct_answer, user_answer, is_correct)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                telegram_id, session_id, domain, topic, question_text,
                correct_answer, user_answer, int(is_correct),
            ),
        )
        await db.commit()


async def get_stats_by_domain(telegram_id: int) -> list[dict]:
    """Return per-domain accuracy for the last 30 answers per domain."""
    async with get_db() as db:
        async with db.execute(
            """SELECT domain,
                      COUNT(*) as total,
                      SUM(is_correct) as correct
               FROM answers
               WHERE telegram_id = ?
               GROUP BY domain""",
            (telegram_id,),
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def get_weak_domains(telegram_id: int, threshold: float = 0.6) -> list[str]:
    """Domains where accuracy is below threshold."""
    stats = await get_stats_by_domain(telegram_id)
    weak = []
    for s in stats:
        if s["total"] >= 3 and (s["correct"] / s["total"]) < threshold:
            weak.append(s["domain"])
    return weak


async def get_recent_topics(telegram_id: int, n: int = 5) -> list[str]:
    """Last n topics answered by the user (to avoid repetition)."""
    async with get_db() as db:
        async with db.execute(
            """SELECT DISTINCT topic FROM answers
               WHERE telegram_id = ?
               ORDER BY answered_at DESC
               LIMIT ?""",
            (telegram_id, n),
        ) as cur:
            rows = await cur.fetchall()
            return [r["topic"] for r in rows]
