"""Slash command handlers: /start, /progress, /readiness, /reset, /help, /domain"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from bot.conversation import DOMAINS, DOMAIN_EMOJIS, State, get_user_state, set_state
from db import models
from core.scorer import compute_readiness


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await models.upsert_user(user.id, user.username or user.first_name)

    state = get_user_state(context, user.id)
    set_state(context, user.id, State.CHOOSING_DOMAIN)

    keyboard = [
        [InlineKeyboardButton(f"{DOMAIN_EMOJIS[d]} {d}", callback_data=f"domain:{d}")]
        for d in DOMAINS
    ]
    await update.message.reply_text(
        f"👋 Hey {user.first_name}! I'm your AZ-900 study tutor.\n\n"
        "I'll quiz you with scenario questions and give you Socratic feedback — "
        "not just 'right/wrong', but *why*.\n\n"
        "Which domain do you want to drill?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_domain(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Let user switch domain mid-session."""
    set_state(context, update.effective_user.id, State.CHOOSING_DOMAIN)
    keyboard = [
        [InlineKeyboardButton(f"{DOMAIN_EMOJIS[d]} {d}", callback_data=f"domain:{d}")]
        for d in DOMAINS
    ]
    await update.message.reply_text(
        "Which domain do you want to switch to?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def cmd_progress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    stats = await models.get_stats_by_domain(user_id)

    if not stats:
        await update.message.reply_text(
            "No answers recorded yet. Use /start to begin a session!"
        )
        return

    lines = ["📊 *Your Progress*\n"]
    for s in stats:
        pct = int(s["correct"] / s["total"] * 100)
        bar = _progress_bar(pct)
        lines.append(f"{DOMAIN_EMOJIS.get(s['domain'], '•')} *{s['domain']}*")
        lines.append(f"  {bar} {pct}% ({s['correct']}/{s['total']} correct)\n")

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_readiness(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    stats = await models.get_stats_by_domain(user_id)

    if not stats or sum(s["total"] for s in stats) < 5:
        await update.message.reply_text(
            "Answer at least 5 questions first to get a readiness score. "
            "Use /start to begin!"
        )
        return

    score, breakdown = compute_readiness(stats)
    lines = ["🎯 *Exam Readiness Score*\n"]
    for domain, pct in breakdown.items():
        emoji = "✅" if pct >= 80 else ("⚠️" if pct >= 60 else "❌")
        lines.append(f"{emoji} {domain}: {pct}%")

    lines.append(f"\n*Overall: {score}% ready*")

    if score >= 80:
        lines.append("\n🚀 You're ready to book the exam!")
    elif score >= 60:
        lines.append("\n📚 Getting there! Focus on your weak areas.")
    else:
        lines.append("\n💪 Keep drilling — consistency beats cramming.")

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    state = get_user_state(context, user_id)
    state.update({
        "state": State.IDLE,
        "domain": None,
        "session_id": None,
        "current_question": None,
        "conversation_history": [],
    })
    await update.message.reply_text(
        "Session reset. Use /start to begin a new session."
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "*AZ-900 Tutor Commands*\n\n"
        "/start — Start a new study session\n"
        "/domain — Switch to a different domain\n"
        "/progress — See your accuracy per domain\n"
        "/readiness — Get your overall exam readiness score\n"
        "/reset — Clear your current session\n"
        "/help — Show this message\n\n"
        "*How it works:*\n"
        "1. Pick a domain\n"
        "2. Get a scenario question\n"
        "3. Reply with A, B, C, or D\n"
        "4. Get Socratic feedback + a follow-up\n"
        "5. Repeat!",
        parse_mode=ParseMode.MARKDOWN,
    )


def _progress_bar(pct: int, width: int = 10) -> str:
    filled = round(pct / 100 * width)
    return "█" * filled + "░" * (width - filled)
