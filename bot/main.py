"""
Telegram bot entry point.
Handles domain selection callbacks and the main answer→feedback loop.
"""

import asyncio
import logging
import os
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from telegram.constants import ParseMode

from bot.commands import (
    cmd_start, cmd_domain, cmd_progress,
    cmd_readiness, cmd_reset, cmd_help,
)
from bot.conversation import (
    DOMAINS, DOMAIN_EMOJIS, State,
    get_user_state, set_state, set_question, get_question,
    append_history, clear_history,
)
from core.tutor import generate_question, format_question_message, evaluate_answer, generate_explain_back_prompt, evaluate_explanation
from core.retriever import is_ready
from db.database import init_db
from db import models

load_dotenv()
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ── Domain selection callback ──────────────────────────────────────────────

async def on_domain_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    domain = query.data.replace("domain:", "")
    if domain not in DOMAINS:
        return

    user_id = query.from_user.id
    state = get_user_state(context, user_id)
    state["domain"] = domain
    clear_history(context, user_id)

    await models.set_user_domain(user_id, domain)
    session_id = await models.start_session(user_id, domain)
    state["session_id"] = session_id

    await query.edit_message_text(
        f"{DOMAIN_EMOJIS[domain]} Starting *{domain}* session...",
        parse_mode=ParseMode.MARKDOWN,
    )

    await _send_next_question(context, user_id, query.message.chat_id, domain)


# ── Send a question ────────────────────────────────────────────────────────

async def _send_next_question(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    chat_id: int,
    domain: str,
):
    recent_topics = await models.get_recent_topics(user_id, n=10)

    await context.bot.send_message(chat_id, "⏳ Generating question...")

    loop = asyncio.get_event_loop()
    question = await loop.run_in_executor(
        None, lambda: generate_question(domain, recent_topics)
    )

    set_question(context, user_id, question)
    set_state(context, user_id, State.WAITING_ANSWER)

    text = format_question_message(question)
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("A", callback_data="ans:A"),
            InlineKeyboardButton("B", callback_data="ans:B"),
            InlineKeyboardButton("C", callback_data="ans:C"),
            InlineKeyboardButton("D", callback_data="ans:D"),
        ]
    ])

    await context.bot.send_message(
        chat_id,
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard,
    )


# ── Answer via button ──────────────────────────────────────────────────────

async def on_answer_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    state = get_user_state(context, user_id)

    if state["state"] != State.WAITING_ANSWER:
        return

    letter = query.data.replace("ans:", "")
    await query.edit_message_reply_markup(reply_markup=None)  # remove buttons
    await _process_answer(context, user_id, query.message.chat_id, letter)


# ── Answer via free text ───────────────────────────────────────────────────

async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    state = get_user_state(context, user_id)
    text = update.message.text.strip()

    if state["state"] == State.WAITING_ANSWER:
        # Accept A/B/C/D or full option text
        letter = text[0].upper() if text else ""
        if letter not in ("A", "B", "C", "D"):
            await update.message.reply_text(
                "Please reply with A, B, C, or D (or tap a button)."
            )
            return
        await _process_answer(context, user_id, update.message.chat_id, letter)

    elif state["state"] == State.WAITING_EXPLAIN_BACK:
        await _process_explain_back(context, user_id, update.message.chat_id, text)

    else:
        await update.message.reply_text(
            "Use /start to begin a session, or /help to see all commands."
        )


# ── Core answer processing ─────────────────────────────────────────────────

async def _process_answer(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    chat_id: int,
    letter: str,
):
    state = get_user_state(context, user_id)
    question = get_question(context, user_id)
    if not question:
        await context.bot.send_message(chat_id, "Something went wrong. Use /start to restart.")
        return

    await context.bot.send_message(chat_id, "🤔 Thinking...")

    loop = asyncio.get_event_loop()
    feedback, is_correct = await loop.run_in_executor(
        None,
        lambda: evaluate_answer(
            question, letter, state["conversation_history"]
        ),
    )

    await models.record_answer(
        telegram_id=user_id,
        session_id=state["session_id"],
        domain=state["domain"],
        topic=question["topic"],
        question_text=question["question"],
        correct_answer=question["answer"],
        user_answer=letter,
        is_correct=is_correct,
    )

    append_history(context, user_id, "user", f"I answered {letter}")
    append_history(context, user_id, "assistant", feedback)

    result_prefix = "✅" if is_correct else "❌"
    await context.bot.send_message(
        chat_id,
        f"{result_prefix} *You chose {letter}*\n\n{feedback}",
        parse_mode=ParseMode.MARKDOWN,
    )

    if is_correct:
        explain_prompt = await loop.run_in_executor(
            None, lambda: generate_explain_back_prompt(question["topic"])
        )
    else:
        correct_letter = question["answer"]
        correct_text = question["options"].get(correct_letter, "")
        explain_prompt = (
            f"The correct answer was *{correct_letter}) {correct_text}*.\n\n"
            f"In your own words, can you explain why that's the right choice?"
        )

    set_state(context, user_id, State.WAITING_EXPLAIN_BACK)
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⏭ Skip — next question", callback_data="skip_explain")]
    ])
    await context.bot.send_message(
        chat_id,
        explain_prompt,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN,
    )


async def _process_explain_back(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    chat_id: int,
    explanation: str,
):
    """Evaluate the explanation with Claude and move on."""
    append_history(context, user_id, "user", explanation)
    question = get_question(context, user_id)

    await context.bot.send_message(chat_id, "🤔 Evaluating your explanation...")

    loop = asyncio.get_event_loop()
    feedback = await loop.run_in_executor(
        None, lambda: evaluate_explanation(question, explanation)
    )

    append_history(context, user_id, "assistant", feedback)
    await context.bot.send_message(chat_id, feedback)
    await _offer_next_question(context, user_id, chat_id)


async def on_skip_explain(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)
    await _offer_next_question(context, query.from_user.id, query.message.chat_id)


async def _offer_next_question(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    chat_id: int,
):
    state = get_user_state(context, user_id)
    domain = state["domain"]

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➡️ Next question", callback_data="next_question"),
            InlineKeyboardButton("🔀 Switch domain", callback_data="switch_domain"),
        ]
    ])
    await context.bot.send_message(
        chat_id,
        f"Current domain: *{domain}*",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard,
    )
    set_state(context, user_id, State.IDLE)


async def on_next_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)

    user_id = query.from_user.id
    domain = get_user_state(context, user_id)["domain"]
    await _send_next_question(context, user_id, query.message.chat_id, domain)


async def on_switch_domain(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{DOMAIN_EMOJIS[d]} {d}", callback_data=f"domain:{d}")]
        for d in DOMAINS
    ])
    await query.edit_message_text(
        "Which domain do you want to switch to?",
        reply_markup=keyboard,
    )
    set_state(context, query.from_user.id, State.CHOOSING_DOMAIN)


# ── App bootstrap ──────────────────────────────────────────────────────────

def main():
    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_TOKEN not set in environment")

    if not is_ready():
        logger.warning(
            "Vector store not built yet. Run: python -m core.ingest\n"
            "The bot will work but questions won't be grounded in the PDF."
        )

    app = (
        Application.builder()
        .token(token)
        .post_init(lambda app: init_db())
        .build()
    )

    # Commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("domain", cmd_domain))
    app.add_handler(CommandHandler("progress", cmd_progress))
    app.add_handler(CommandHandler("readiness", cmd_readiness))
    app.add_handler(CommandHandler("reset", cmd_reset))
    app.add_handler(CommandHandler("help", cmd_help))

    # Callbacks
    app.add_handler(CallbackQueryHandler(on_domain_selected, pattern=r"^domain:"))
    app.add_handler(CallbackQueryHandler(on_answer_button, pattern=r"^ans:"))
    app.add_handler(CallbackQueryHandler(on_next_question, pattern=r"^next_question$"))
    app.add_handler(CallbackQueryHandler(on_switch_domain, pattern=r"^switch_domain$"))
    app.add_handler(CallbackQueryHandler(on_skip_explain, pattern=r"^skip_explain$"))

    # Free-text messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))

    logger.info("Bot started. Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
