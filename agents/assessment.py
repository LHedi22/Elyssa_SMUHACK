# agents/assessment.py
from rag.retriever import hybrid_search
from agents.supervision import check_grounding
from models.model_loader import call_llm
import config
import json

DIFFICULTY_MAP = {
    "easy":   "foundational recall and definition questions",
    "medium": "application and problem-solving questions",
    "hard":   "analysis, edge cases, and comparison questions"
}

QUIZ_SYSTEM = """You are an educational assessment generator.
Generate exactly 10 multiple-choice questions as a JSON array.

Return ONLY this JSON structure, nothing else:
[
  {
    "question": "...",
    "options": {"A": "...", "B": "...", "C": "...", "D": "..."},
    "answer": "A",
    "rationale": "..."
  },
  ...
]

Rules:
- Exactly 10 questions. No more, no less.
- Use ONLY the provided course material.
- Each question must have exactly 4 options A B C D.
- answer must be exactly one of: A, B, C, or D.
- Questions must vary — do not repeat the same concept twice.
- Return raw JSON only. No markdown, no backticks, no explanation."""


def generate_quiz(course_id: str,
                  chapter: str,
                  difficulty: str) -> list[dict]:
    """
    Generate 10 MCQ questions for a given chapter and difficulty.
    Returns a list of question dicts.
    """
    chunks = hybrid_search(
        course_id, chapter, chapter_filter=chapter
    )

    if not chunks:
        return []

    # Use top 5 chunks for more variety across 10 questions
    context = "\n\n---\n\n".join([c["text"] for c in chunks[:5]])
    diff_desc = DIFFICULTY_MAP.get(difficulty, DIFFICULTY_MAP["medium"])

    user_prompt = f"""Course material from {chapter}:
{context}

Generate exactly 10 {diff_desc} multiple-choice questions
strictly based on the material above.
Return only the JSON array."""

    raw = call_llm(
        config.ASSESSMENT_MODEL,
        QUIZ_SYSTEM,
        user_prompt,
        temperature=0.6
    )

    # ── Parse JSON ────────────────────────────────────────────
    questions = _parse_questions(raw)

    # ── Fallback: if we got fewer than 10, try once more ─────
    if len(questions) < 5:
        print(f"[assessment] Only got {len(questions)} questions, retrying...")
        raw2      = call_llm(
            config.ASSESSMENT_MODEL,
            QUIZ_SYSTEM,
            user_prompt,
            temperature=0.7
        )
        questions = _parse_questions(raw2)

    return questions[:10]


def _parse_questions(raw: str) -> list[dict]:
    """Robustly parse JSON from LLM output."""
    # Strip markdown code fences if present
    cleaned = raw.strip()
    if "```" in cleaned:
        import re
        match   = re.search(r'\[.*\]', cleaned, re.DOTALL)
        cleaned = match.group() if match else cleaned
    cleaned = cleaned.replace("```json", "").replace("```", "").strip()

    try:
        data = json.loads(cleaned)
        if isinstance(data, list):
            # Validate each question has required keys
            valid = []
            for q in data:
                if all(k in q for k in
                       ["question", "options", "answer", "rationale"]):
                    # Ensure answer is valid
                    if q["answer"] in ["A", "B", "C", "D"]:
                        valid.append(q)
            return valid
    except json.JSONDecodeError:
        pass

    return []


def generate_hint(course_id: str,
                  question: str,
                  wrong_answer: str) -> str:
    """Socratic hint for a wrong answer."""
    chunks  = hybrid_search(course_id, question)
    context = chunks[0]["text"] if chunks else ""

    system = (
        "You are a Socratic tutor. "
        "Give one short guiding hint. Do NOT reveal the answer. "
        "Maximum 2 sentences."
    )
    user = (
        f"The student answered: '{wrong_answer}'\n"
        f"Relevant material: {context}\n"
        f"Give a hint pointing toward the correct thinking."
    )
    return call_llm(
        config.TUTOR_MODEL, system, user, temperature=0.4
    )