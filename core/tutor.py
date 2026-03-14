"""
Core LLM logic: question generation + Socratic evaluation.
Uses claude-haiku-4-5 for cost efficiency (~$0.001/session).
"""

import os
import json
import random
from pathlib import Path
import anthropic
from core.retriever import get_chunks_for_query

MOCK_MODE = not os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("MOCK_LLM") == "1"

if not MOCK_MODE:
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
MODEL = "claude-haiku-4-5"

_BANK_PATH = Path(__file__).parent.parent / "data" / "question_bank.json"
_question_bank: dict[str, list] | None = None


def _load_bank() -> dict[str, list]:
    global _question_bank
    if _question_bank is None:
        if _BANK_PATH.exists():
            _question_bank = json.loads(_BANK_PATH.read_text())
        else:
            _question_bank = {}
    return _question_bank

_MOCK_QUESTION = {
    "topic": "Azure Storage Tiers",
    "question": "A company stores rarely accessed compliance data that must be kept for 7 years. Which Azure Blob Storage access tier minimizes cost?",
    "options": {"A": "Hot", "B": "Cool", "C": "Archive", "D": "Premium"},
    "answer": "C",
    "explanation": "Archive tier is the lowest cost option for data that is rarely accessed and can tolerate retrieval delays.",
}


def generate_question(domain: str, previous_topics: list[str] = None) -> dict:
    """
    Pick a random question from the pre-built question bank for the given domain,
    avoiding recently covered topics. Falls back to live generation if bank is empty.
    """
    if MOCK_MODE:
        return _MOCK_QUESTION

    bank = _load_bank()
    pool = bank.get(domain, [])

    if pool:
        avoid = set(previous_topics[-10:]) if previous_topics else set()
        candidates = [q for q in pool if q.get("topic") not in avoid]
        if not candidates:
            candidates = pool  # all topics covered — reset avoidance
        return random.choice(candidates)

    # Fallback: live generation (used if bank not generated yet)
    chunks = get_chunks_for_query(domain, n=3)
    context = "\n\n".join(chunks) if chunks else f"Azure {domain} concepts"
    avoid_clause = f"\nAvoid: {', '.join(previous_topics[-10:])}" if previous_topics else ""

    prompt = f"""You are creating AZ-900 exam practice questions.
Context: {context}
Domain: {domain}{avoid_clause}

Generate ONE scenario-based multiple-choice question in this exact format:
TOPIC: <topic>
QUESTION: <scenario and question>
A) <option>
B) <option>
C) <option>
D) <option>
ANSWER: <letter>
EXPLANATION: <why correct>"""

    response = client.messages.create(
        model=MODEL, max_tokens=800,
        messages=[{"role": "user", "content": prompt}],
    )
    return _parse_question(response.content[0].text)


def _parse_question(raw: str) -> dict:
    """Parse the structured question response into a dict."""
    lines = raw.strip().splitlines()
    result = {"topic": "", "question": "", "options": {}, "answer": "", "explanation": ""}
    current_key = None

    for line in lines:
        line = line.strip()
        if line.startswith("TOPIC:"):
            result["topic"] = line[6:].strip()
        elif line.startswith("QUESTION:"):
            result["question"] = line[9:].strip()
            current_key = "question"
        elif line.startswith(("A)", "B)", "C)", "D)")):
            letter = line[0]
            result["options"][letter] = line[3:].strip()
        elif line.startswith("ANSWER:"):
            result["answer"] = line[7:].strip().upper()
        elif line.startswith("EXPLANATION:"):
            result["explanation"] = line[12:].strip()
        elif current_key == "question" and line and not any(
            line.startswith(p) for p in ("A)", "B)", "C)", "D)", "ANSWER:", "EXPLANATION:")
        ):
            result["question"] += " " + line

    return result


def format_question_message(q: dict) -> str:
    """Format a question dict into a Telegram-ready message string."""
    options = "\n".join(f"{k}) {v}" for k, v in q["options"].items())
    return f"{q['question']}\n\n{options}"


def evaluate_answer(
    question: dict,
    user_answer: str,
    conversation_history: list[dict],
) -> tuple[str, bool]:
    """
    Evaluate the user's answer as a Socratic tutor.
    Returns (feedback_message, is_correct).
    """
    options_text = "\n".join(f"{k}) {v}" for k, v in question["options"].items())
    is_correct = user_answer.strip().upper().startswith(question["answer"])

    # Get extra context for richer feedback
    context_chunks = get_chunks_for_query(question["topic"], n=2)
    extra_context = "\n".join(context_chunks[:2]) if context_chunks else ""

    system = """You are a friendly, encouraging AZ-900 study tutor.
Your job is to give Socratic feedback — not just say right/wrong, but help the student understand WHY.
Keep responses concise (3-5 sentences). Use plain language, no jargon unless you define it.
End with a short follow-up question to deepen understanding."""

    messages = conversation_history + [
        {
            "role": "user",
            "content": f"""Question: {question['question']}
Options:
{options_text}
Correct answer: {question['answer']}) {question['options'].get(question['answer'], '')}
Student answered: {user_answer.strip()}
Is correct: {is_correct}
Additional context: {extra_context}

Give feedback as the tutor.""",
        }
    ]

    if MOCK_MODE:
        if is_correct:
            return "Correct! Archive tier is ideal for compliance data that's rarely accessed. It has the lowest storage cost but retrieval takes hours. When would you choose Cool over Archive?", True
        return "Not quite. Archive tier would be best here since the data is rarely accessed and cost is the priority. Hot and Cool tiers cost more but allow faster access. Why might retrieval speed matter for some data?", False

    response = client.messages.create(
        model=MODEL,
        max_tokens=400,
        system=system,
        messages=messages,
    )

    return response.content[0].text, is_correct


def evaluate_explanation(question: dict, explanation: str) -> str:
    """Evaluate the user's explanation and give Socratic feedback."""
    correct_letter = question["answer"]
    correct_text = question["options"].get(correct_letter, "")

    if MOCK_MODE:
        return "Good effort! You've captured the key idea. Archive tier is best when data is rarely accessed and you can tolerate slow retrieval — cost savings outweigh access speed."

    prompt = f"""An AZ-900 student was asked to explain the following:

Topic: {question["topic"]}
Question: {question["question"]}
Correct answer: {correct_letter}) {correct_text}

Their explanation: {explanation}

As a Socratic tutor, evaluate their explanation in 2-3 sentences:
- Did they capture the key concept correctly?
- What was good about their explanation?
- What's one thing they could add or clarify?
Be encouraging but honest. If the explanation is completely wrong or gibberish, say so kindly."""

    response = client.messages.create(
        model=MODEL,
        max_tokens=250,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


def chat_followup(message: str, conversation_history: list[dict], domain: str) -> str:
    """Free-form follow-up chat about the current topic/domain."""
    if MOCK_MODE:
        return "Great question! In Azure, the shared responsibility model means Microsoft always handles physical security, while you're responsible for your data and identities regardless of service model."

    system = f"""You are a friendly AZ-900 Azure Fundamentals study tutor helping a student prepare for the exam.
The student is currently studying: {domain}.
Answer their follow-up question clearly and concisely (3-5 sentences).
Relate your answer to AZ-900 exam concepts where relevant.
If they ask something unrelated to Azure/cloud, gently redirect them back to study topics."""

    messages = conversation_history + [{"role": "user", "content": message}]

    response = client.messages.create(
        model=MODEL,
        max_tokens=400,
        system=system,
        messages=messages,
    )
    return response.content[0].text.strip()


def generate_explain_back_prompt(topic: str) -> str:
    """After a correct answer, generate an 'explain it back' challenge."""
    prompt = f"""Generate a one-sentence "explain it back" challenge for an AZ-900 student who just answered a question about "{topic}" correctly.

The challenge should ask them to explain a related concept in their own words, or describe when they would/wouldn't use a service.
Keep it conversational. Start with "Good job! Now..." or similar.
One sentence only."""

    if MOCK_MODE:
        return f"Good job! Now can you explain in your own words when you would choose Archive tier over Cool tier for blob storage?"

    response = client.messages.create(
        model=MODEL,
        max_tokens=100,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()
