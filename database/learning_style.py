# database/learning_style.py
import json
import os

STYLES_FILE = "data/learning_styles.json"

QUESTIONS = [
    {
        "q": "When you try to understand a new concept, what helps you most?",
        "options": {
            "A": "Diagrams, charts, or visual explanations",
            "B": "Listening to someone explain it",
            "C": "Reading written explanations or notes",
            "D": "Trying it yourself or doing an activity"
        }
    },
    {
        "q": "When learning how to use new software or a tool, you prefer:",
        "options": {
            "A": "Watching a visual tutorial",
            "B": "Listening to someone explain the steps",
            "C": "Reading written instructions",
            "D": "Experimenting with the tool yourself"
        }
    },
    {
        "q": "When studying for an exam, what works best for you?",
        "options": {
            "A": "Reviewing diagrams, mind maps, or charts",
            "B": "Discussing topics with others",
            "C": "Reading textbooks or summaries",
            "D": "Practicing problems or exercises"
        }
    },
    {
        "q": "When a teacher explains something complicated, you prefer:",
        "options": {
            "A": "Visual examples or demonstrations",
            "B": "A spoken explanation",
            "C": "Written notes and definitions",
            "D": "Interactive activities or experiments"
        }
    },
    {
        "q": "If you forget how something works, you usually:",
        "options": {
            "A": "Visualize the steps in your mind",
            "B": "Remember what someone said about it",
            "C": "Look up written instructions",
            "D": "Try doing it again until it works"
        }
    },
    {
        "q": "When learning a new topic, you enjoy:",
        "options": {
            "A": "Infographics or diagrams",
            "B": "Lectures or podcasts",
            "C": "Articles or textbooks",
            "D": "Hands-on practice"
        }
    },
    {
        "q": "If you are working in a group project, you prefer to:",
        "options": {
            "A": "Create diagrams or visual presentations",
            "B": "Explain ideas verbally to the team",
            "C": "Write documentation or notes",
            "D": "Build prototypes or test ideas"
        }
    },
    {
        "q": "What type of learning material do you prefer most?",
        "options": {
            "A": "Charts, graphs, and images",
            "B": "Recorded explanations or discussions",
            "C": "Written guides or manuals",
            "D": "Simulations, labs, or experiments"
        }
    },
    {
        "q": "When remembering information, you often:",
        "options": {
            "A": "Recall pictures or diagrams",
            "B": "Remember what was said in class",
            "C": "Remember written notes or text",
            "D": "Remember what you physically did"
        }
    },
    {
        "q": "Which activity sounds most appealing when learning something new?",
        "options": {
            "A": "Watching a visual explanation",
            "B": "Listening to a lecture or explanation",
            "C": "Reading an article about it",
            "D": "Doing a practical exercise"
        }
    }
]

STYLE_MAP = {
    "A": "Visual",
    "B": "Auditory",
    "C": "Reading/Writing",
    "D": "Kinesthetic"
}

STYLE_DESCRIPTIONS = {
    "Visual": {
        "emoji":       "👁",
        "tagline":     "You think in pictures and diagrams.",
        "best_with":   [
            "Diagrams and charts",
            "Mind maps",
            "Visual explanations",
            "Colour-coded notes"
        ],
        "tutor_adapt": (
            "Elyssa will guide you using structured visual "
            "comparisons, step-by-step breakdowns, and "
            "diagram-style explanations."
        )
    },
    "Auditory": {
        "emoji":       "🎧",
        "tagline":     "You learn best through conversation.",
        "best_with":   [
            "Verbal explanations",
            "Discussions",
            "Lectures and podcasts",
            "Talking through problems"
        ],
        "tutor_adapt": (
            "Elyssa will use a conversational, dialogue-driven "
            "style — explaining concepts through back-and-forth "
            "discussion rather than dense text."
        )
    },
    "Reading/Writing": {
        "emoji":       "📖",
        "tagline":     "You absorb information through text.",
        "best_with":   [
            "Written summaries",
            "Structured notes",
            "Textbooks and articles",
            "Step-by-step written guides"
        ],
        "tutor_adapt": (
            "Elyssa will give you well-structured written "
            "explanations, definitions, and summaries you can "
            "reference and re-read."
        )
    },
    "Kinesthetic": {
        "emoji":       "🤝",
        "tagline":     "You learn by doing.",
        "best_with":   [
            "Hands-on practice",
            "Exercises and problems",
            "Experiments",
            "Building and testing"
        ],
        "tutor_adapt": (
            "Elyssa will prioritise practice problems, worked "
            "examples, and quiz-based learning over abstract "
            "explanations."
        )
    }
}


def score_quiz(answers: dict) -> dict:
    """
    answers = {0: 'A', 1: 'C', ...}  (question_index: answer)
    Returns {style: count, ..., dominant: style}
    """
    counts = {"Visual": 0, "Auditory": 0,
              "Reading/Writing": 0, "Kinesthetic": 0}

    for answer in answers.values():
        style = STYLE_MAP.get(answer.upper())
        if style:
            counts[style] += 1

    dominant = max(counts, key=counts.get)
    return {**counts, "dominant": dominant}


def save_style(student_id: str, result: dict):
    """Persist learning style result to disk."""
    os.makedirs("data", exist_ok=True)
    data = {}
    if os.path.exists(STYLES_FILE):
        with open(STYLES_FILE, "r") as f:
            data = json.load(f)
    data[student_id] = result
    with open(STYLES_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_style(student_id: str) -> dict | None:
    """Load saved learning style for a student."""
    if not os.path.exists(STYLES_FILE):
        return None
    with open(STYLES_FILE, "r") as f:
        data = json.load(f)
    return data.get(student_id)