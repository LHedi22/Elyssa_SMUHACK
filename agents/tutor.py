# agents/tutor.py
from rag.retriever import hybrid_search
from agents.supervision import check_grounding, FALLBACK_MESSAGE
from models.model_loader import call_llm
import config

# ── System prompts — all demand SHORT output ──────────────────

CLASSIFY_SYSTEM = """You are a classifier. Reply with exactly one word only.

Given a tutor's last question and the student's reply, classify the reply:

UNDERSTOOD   - student answered correctly or showed clear understanding
WRONG        - student tried to answer but got it wrong
DONT_KNOW    - student said they don't know, unsure, or gave no real answer
IRRELEVANT   - student said something unrelated to the topic
QUESTION     - student is asking a new or follow-up question

One word only. No punctuation. No explanation."""


GUIDING_QUESTION_SYSTEM = """You are StudyMate, a Socratic tutor.

Rules:
- Ask exactly ONE short guiding question. Nothing else.
- Maximum 2 sentences.
- Do not explain. Do not answer. Do not compliment.
- Base your question ONLY on the course material provided.
- Start directly with the question."""


BRIEF_EXPLAIN_SYSTEM = """You are StudyMate, a Socratic tutor.

The student said they don't know. Give a brief explanation then ask one guiding question.

Rules:
- Explanation: maximum 2-3 sentences. Use ONLY the course material.
- Then ask ONE short follow-up question to check understanding.
- Total response: maximum 5 sentences.
- Do not repeat the course material verbatim."""


WRONG_ANSWER_SYSTEM = """You are StudyMate, a Socratic tutor.

The student gave a wrong answer. Give a short hint and ask one guiding question.

Rules:
- One sentence acknowledging they are on the wrong track.
- One sentence hint pointing in the right direction.
- One guiding question.
- Total: 3 sentences maximum.
- Do not reveal the full answer."""


FULL_EXPLAIN_SYSTEM = """You are StudyMate, a Socratic tutor.

The student understood. Give a clear explanation then ask a follow-up question.

Rules:
- Explanation: 3-4 sentences maximum. Use ONLY the course material.
- End with ONE follow-up question to go deeper.
- Do not include raw course material text.
- Cite source at the very end: (Source: filename, chapter)"""


IRRELEVANT_SYSTEM = """You are StudyMate, a Socratic tutor.

The student said something unrelated to the current topic.

Rules:
- One sentence flagging this politely.
- One sentence redirecting back to the topic.
- Maximum 2 sentences total.
respond with a short message that redirects them back to the topic being discussed. Do not acknowledge the irrelevant comment beyond the first sentence.
"""


def _classify_reply(tutor_question: str, student_reply: str) -> str:
    """Classify the student's reply into one of 5 categories."""
    prompt = f"""Tutor asked: "{tutor_question}"
Student replied: "{student_reply}"

Classify the student's reply."""

    result = call_llm(
        config.TUTOR_MODEL,
        CLASSIFY_SYSTEM,
        prompt,
        temperature=0.0
    ).strip().upper()

    # Clean up — only keep the first word
    first_word = result.split()[0] if result else "QUESTION"
    valid = {"UNDERSTOOD", "WRONG", "DONT_KNOW", "IRRELEVANT", "QUESTION"}
    return first_word if first_word in valid else "QUESTION"


def answer_question(course_id: str, question: str,
                    history: list = None) -> dict:
    history = history or []

    # ── Retrieve relevant chunks ──────────────────────────────
    chunks = hybrid_search(course_id, question)

    # ── Guard: no relevant content found ─────────────────────
    if not chunks:
        return {
            "answer": (
                "I could not find any relevant content "
                "in your course materials for this question.\n\n"
                "Try uploading lecture notes or slides that "
                "cover this topic, then ask again."
            ),
            "source":     None,
            "confidence": 0.0,
            "phase":      "no_content"
        }

    # Top 2 chunks only — keeps context short and focused
    context = "\n---\n".join([c["text"] for c in chunks[:2]])

    # ── First message — no history yet ───────────────────────
    # Just ask the first guiding question
    if not history:
        prompt = f"""Course material:
{context}

Student asked: {question}

Ask one short guiding question."""

        raw = call_llm(
            config.TUTOR_MODEL,
            GUIDING_QUESTION_SYSTEM,
            prompt,
            temperature=0.4
        )
        return {
            "answer":     raw,
            "source":     None,
            "confidence": 1.0,
            "phase":      "question"
        }

    # ── Classify the student's latest reply ──────────────────
    last_tutor_message = history[-1].get("a", "") if history else ""
    classification = _classify_reply(last_tutor_message, question)

    # ── Route to correct response type ───────────────────────

    # IRRELEVANT — flag and redirect
    if classification == "IRRELEVANT":
        last_topic = history[-1].get("q", "the current topic") if history else "the current topic"
        prompt = f"""The student went off-topic. 
The current topic being discussed: "{last_tutor_message}"
Student said: "{question}"
Redirect them back."""

        raw = call_llm(
            config.TUTOR_MODEL,
            IRRELEVANT_SYSTEM,
            prompt,
            temperature=0.3
        )
        return {
            "answer":     raw,
            "source":     None,
            "confidence": 1.0,
            "phase":      "redirect"
        }

    # DONT_KNOW — brief explanation + next guiding question
    if classification == "DONT_KNOW":
        prompt = f"""Course material:
{context}

The student does not know the answer to: "{last_tutor_message}"

Briefly explain it and ask a follow-up guiding question."""

        raw = call_llm(
            config.TUTOR_MODEL,
            BRIEF_EXPLAIN_SYSTEM,
            prompt,
            temperature=0.3
        )
        grounding = check_grounding(raw, chunks)
        return {
            "answer":     raw,
            "source":     None,
            "confidence": grounding["score"],
            "phase":      "brief_explain"
        }

    # WRONG — hint + redirect question
    if classification == "WRONG":
        prompt = f"""Course material:
{context}

Tutor asked: "{last_tutor_message}"
Student answered wrongly: "{question}"

Give a short hint and one guiding question."""

        raw = call_llm(
            config.TUTOR_MODEL,
            WRONG_ANSWER_SYSTEM,
            prompt,
            temperature=0.3
        )
        return {
            "answer":     raw,
            "source":     None,
            "confidence": 1.0,
            "phase":      "hint"
        }

    # UNDERSTOOD — full explanation + follow-up question
    if classification == "UNDERSTOOD":
        prompt = f"""Course material:
{context}

Conversation:
Tutor: {last_tutor_message}
Student: {question}

Give a short explanation and one deeper follow-up question."""

        raw = call_llm(
            config.TUTOR_MODEL,
            FULL_EXPLAIN_SYSTEM,
            prompt,
            temperature=0.3
        )
        grounding = check_grounding(raw, chunks)

        if grounding["verdict"] == "fallback":
            return {
                "answer":     FALLBACK_MESSAGE,
                "source":     None,
                "confidence": 0.0,
                "phase":      "fallback"
            }

        src      = grounding["source"]
        citation = f"*Source: {src['filename']}, {src['chapter']}*"
        return {
            "answer":     raw,
            "source":     citation,
            "confidence": grounding["score"],
            "phase":      "explanation"
        }

    # QUESTION — treat as a new question, ask guiding question
    prompt = f"""Course material:
{context}

Previous conversation:
{chr(10).join([f"Tutor: {t['a']}" for t in history[-2:]])}

Student asks: {question}

Ask one short guiding question."""

    raw = call_llm(
        config.TUTOR_MODEL,
        GUIDING_QUESTION_SYSTEM,
        prompt,
        temperature=0.4
    )
    return {
        "answer":     raw,
        "source":     None,
        "confidence": 1.0,
        "phase":      "question"
    }