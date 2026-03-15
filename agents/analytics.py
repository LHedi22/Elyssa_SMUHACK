# agents/analytics.py
from database.mongo_client import log_event, get_events
from sklearn.linear_model import LogisticRegression
import numpy as np

# BKT default parameters (can be calibrated per course)
BKT_DEFAULTS = {"p_l0": 0.15, "p_t": 0.30, "p_s": 0.10, "p_g": 0.25}

def update_bkt(p_l: float, correct: bool,
               params: dict = BKT_DEFAULTS) -> float:
    """Run one BKT update step. Returns new P(mastery)."""
    p_s, p_g = params["p_s"], params["p_g"]
    p_t = params["p_t"]

    if correct:
        p_correct = p_l * (1 - p_s) + (1 - p_l) * p_g
        p_l_obs = (p_l * (1 - p_s)) / p_correct
    else:
        p_incorrect = p_l * p_s + (1 - p_l) * (1 - p_g)
        p_l_obs = (p_l * p_s) / p_incorrect

    # Apply learning transition
    p_l_new = p_l_obs + (1 - p_l_obs) * p_t
    return round(min(p_l_new, 0.999), 4)

def compute_risk_score(mastery_scores: list[float],
                       days_since_login: int,
                       quiz_attempt_rate: float,
                       mastery_trend: float) -> float:
    """
    Logistic regression risk score.
    In production this model is trained on historical data.
    Here we use a hand-calibrated weight vector.
    """
    mean_mastery = np.mean(mastery_scores) if mastery_scores else 0.5
    min_mastery  = np.min(mastery_scores)  if mastery_scores else 0.5

    # Feature vector: [mean_mastery, min_mastery, login_recency,
    #                  quiz_rate, mastery_trend]
    features = np.array([[
        mean_mastery,
        min_mastery,
        min(days_since_login / 14.0, 1.0),  # normalise to 2-week window
        1.0 - quiz_attempt_rate,             # low rate = higher risk
        -mastery_trend                        # negative trend = higher risk
    ]])

    # Calibrated weights (train this on real data when available)
    weights = np.array([-2.5, -1.8, 1.4, 1.2, 0.9])
    bias    = 0.3

    log_odds = float(np.dot(features, weights) + bias)
    risk     = 1 / (1 + np.exp(-log_odds))
    return round(float(risk), 3)

def record_quiz_result(student_id: str, course_id: str,
                       topic: str, correct: bool,
                       current_mastery: float) -> float:
    """Update BKT and log event. Returns new mastery."""
    new_mastery = update_bkt(current_mastery, correct)
    log_event(student_id, course_id, {
        "type":        "quiz_answer",
        "topic":       topic,
        "correct":     correct,
        "old_mastery": current_mastery,
        "new_mastery": new_mastery
    })
    return new_mastery