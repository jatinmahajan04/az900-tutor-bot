"""
Conversation state machine.
Each user has a state dict stored in bot_data (in-memory, survives restarts via pickle).
"""

from enum import Enum, auto


class State(str, Enum):
    IDLE = "idle"
    CHOOSING_DOMAIN = "choosing_domain"
    WAITING_ANSWER = "waiting_answer"
    WAITING_EXPLAIN_BACK = "waiting_explain_back"


DOMAINS = [
    "Cloud Concepts",
    "Azure Architecture and Services",
    "Azure Management and Governance",
]

DOMAIN_EMOJIS = {
    "Cloud Concepts": "☁️",
    "Azure Architecture and Services": "🏗️",
    "Azure Management and Governance": "⚙️",
}


def get_user_state(context, user_id: int) -> dict:
    """Get or initialise state for a user."""
    if "users" not in context.bot_data:
        context.bot_data["users"] = {}
    if user_id not in context.bot_data["users"]:
        context.bot_data["users"][user_id] = {
            "state": State.IDLE,
            "domain": None,
            "session_id": None,
            "current_question": None,
            "conversation_history": [],
        }
    return context.bot_data["users"][user_id]


def set_state(context, user_id: int, state: State):
    get_user_state(context, user_id)["state"] = state


def set_question(context, user_id: int, question: dict):
    get_user_state(context, user_id)["current_question"] = question


def get_question(context, user_id: int) -> dict | None:
    return get_user_state(context, user_id).get("current_question")


def append_history(context, user_id: int, role: str, content: str):
    history = get_user_state(context, user_id)["conversation_history"]
    history.append({"role": role, "content": content})
    # Keep last 6 turns to stay within token budget
    if len(history) > 12:
        history[:] = history[-12:]


def clear_history(context, user_id: int):
    get_user_state(context, user_id)["conversation_history"] = []
