# agents/orchestrator.py
from models.model_loader import load_intent_classifier

_classifier = load_intent_classifier()
INTENT_LABELS = [
    "asking a tutoring question about course content",
    "requesting to take a quiz or practice questions",
]

def classify_intent(message: str) -> str:
    """Returns 'tutor' or 'quiz'."""
    result = _classifier(message, INTENT_LABELS)
    top_label = result["labels"][0]
    return "quiz" if "quiz" in top_label else "tutor"