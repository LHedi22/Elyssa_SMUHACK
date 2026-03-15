# agents/analytics.py  — full replacement
from database.mongo_client import (
    log_event, get_events,
    update_mastery, get_mastery,
    get_topic_interactions
)
import numpy as np

BKT_DEFAULTS = {
    "p_l0": 0.15,
    "p_t":  0.30,
    "p_s":  0.10,
    "p_g":  0.25
}


def update_bkt(p_l: float,
               correct: bool,
               params: dict = BKT_DEFAULTS) -> float:
    """Run one BKT update. Returns new P(mastery)."""
    p_s, p_g, p_t = params["p_s"], params["p_g"], params["p_t"]

    if correct:
        p_correct  = p_l * (1 - p_s) + (1 - p_l) * p_g
        p_l_obs    = (p_l * (1 - p_s)) / p_correct
    else:
        p_incorrect = p_l * p_s + (1 - p_l) * (1 - p_g)
        p_l_obs     = (p_l * p_s) / p_incorrect

    p_l_new = p_l_obs + (1 - p_l_obs) * p_t
    return round(min(float(p_l_new), 0.999), 4)


def detect_topic_from_chunks(chunks: list[dict]) -> str:
    """
    Infer the most likely chapter/topic from
    retrieved RAG chunks. Uses the most common
    chapter tag across the top chunks.
    """
    if not chunks:
        return "General"

    from collections import Counter
    chapters = [
        c.get("meta", {}).get("chapter", "General")
        for c in chunks
    ]
    most_common = Counter(chapters).most_common(1)
    return most_common[0][0] if most_common else "General"


def record_quiz_result(student_id: str,
                       course_id: str,
                       topic: str,
                       correct: bool,
                       current_mastery: float) -> float:
    """
    Update BKT after a quiz answer.
    Stores result in MongoDB and returns new mastery.
    """
    new_mastery = update_bkt(current_mastery, correct)

    # Persist to MongoDB
    update_mastery(
        student_id, course_id, topic,
        new_mastery, source="quiz"
    )

    # Log the event
    log_event(student_id, course_id, {
        "type":        "quiz_answer",
        "topic":       topic,
        "correct":     correct,
        "old_mastery": current_mastery,
        "new_mastery": new_mastery
    })

    return new_mastery


def record_tutor_interaction(student_id: str,
                              course_id: str,
                              topic: str,
                              phase: str,
                              understood: bool = False):
    """
    Update mastery after a tutor chat interaction.

    Rules:
    - Asking a question: very small positive signal (+0.02)
    - Receiving explanation (phase=explanation): medium signal (+0.05)
    - Student showed understanding: larger signal (+0.08)
    - Wrong answer / redirect: no mastery change
    """
    doc     = get_topic_interactions(
        student_id, course_id, topic
    )
    current = doc.get("mastery", 0.15)

    # Mastery bump depends on interaction quality
    if phase == "explanation" and understood:
        bump = 0.08
    elif phase == "explanation":
        bump = 0.05
    elif phase in ["question", "brief_explain"]:
        bump = 0.02
    else:
        # hint, redirect, fallback — no change
        return current

    new_mastery = round(
        min(current + bump, 0.999), 4
    )

    update_mastery(
        student_id, course_id, topic,
        new_mastery, source="tutor"
    )

    log_event(student_id, course_id, {
        "type":        "tutor_interaction",
        "topic":       topic,
        "phase":       phase,
        "understood":  understood,
        "old_mastery": current,
        "new_mastery": new_mastery
    })

    return new_mastery


def record_question_asked(student_id: str,
                           course_id: str,
                           topic: str):
    """
    Small mastery signal just for asking a question.
    Engagement itself is a positive learning signal.
    """
    doc     = get_topic_interactions(
        student_id, course_id, topic
    )
    current = doc.get("mastery", 0.15)

    # Tiny bump for engagement (+0.01, capped at 0.40
    # so just asking questions can't fake mastery)
    if current < 0.40:
        new_mastery = round(current + 0.01, 4)
        update_mastery(
            student_id, course_id, topic,
            new_mastery, source="question"
        )
        log_event(student_id, course_id, {
            "type":    "question_asked",
            "topic":   topic,
            "mastery": new_mastery
        })
        return new_mastery

    return current


def compute_risk_score(mastery_scores: list[float],
                       days_since_login: int = 0,
                       quiz_attempt_rate: float = 0.5,
                       mastery_trend: float = 0.0) -> float:
    """Logistic regression risk score."""
    if not mastery_scores:
        return 0.5

    mean_m = float(np.mean(mastery_scores))
    min_m  = float(np.min(mastery_scores))

    # Use a flat 1D array instead of (1,5) to avoid
    # dot product returning an array instead of scalar
    features = np.array([
        mean_m,
        min_m,
        min(days_since_login / 14.0, 1.0),
        1.0 - quiz_attempt_rate,
        -mastery_trend
    ])

    weights  = np.array([-2.5, -1.8, 1.4, 1.2, 0.9])
    bias     = 0.3

    log_odds = float(np.dot(features, weights) + bias)
    return round(1 / (1 + np.exp(-log_odds)), 3)