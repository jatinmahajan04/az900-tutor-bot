"""SQLite database setup and connection management."""

import aiosqlite
from contextlib import asynccontextmanager
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "tutor.db"


@asynccontextmanager
async def get_db():
    DB_PATH.parent.mkdir(exist_ok=True)
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA journal_mode=WAL")
        yield db


async def init_db():
    """Create all tables on first run."""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                telegram_id   INTEGER PRIMARY KEY,
                username      TEXT,
                current_domain TEXT DEFAULT 'Cloud Concepts',
                created_at    TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id   INTEGER NOT NULL,
                domain        TEXT NOT NULL,
                started_at    TEXT DEFAULT (datetime('now')),
                ended_at      TEXT,
                FOREIGN KEY (telegram_id) REFERENCES users(telegram_id)
            );

            CREATE TABLE IF NOT EXISTS answers (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id   INTEGER NOT NULL,
                session_id    INTEGER,
                domain        TEXT NOT NULL,
                topic         TEXT NOT NULL,
                question_text TEXT NOT NULL,
                correct_answer TEXT NOT NULL,
                user_answer   TEXT NOT NULL,
                is_correct    INTEGER NOT NULL,  -- 0 or 1
                answered_at   TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (telegram_id) REFERENCES users(telegram_id),
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            );
        """)
        await db.commit()
