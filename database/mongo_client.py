# database/mongo_client.py
from pymongo import MongoClient
from datetime import datetime, timezone
import config

_client = MongoClient(config.MONGO_URI)
_db     = _client[config.MONGO_DB_NAME]

# ── Collections ───────────────────────────────────────────────
events_col   = _db["events"]
students_col = _db["students"]
mastery_col  = _db["mastery"]


def log_event(student_id: str, course_id: str, data: dict):
    """Append a student interaction event to the log."""
    events_col.insert_one({
        "student_id": student_id,
        "course_id":  course_id,
        "timestamp":  datetime.now(timezone.utc),
        **data
    })


def get_events(student_id: str, course_id: str) -> list:
    """Return all events for a student in a course."""
    return list(events_col.find(
        {"student_id": student_id, "course_id": course_id},
        {"_id": 0}
    ).sort("timestamp", -1))


def get_all_students(course_id: str) -> list:
    """Return summary list of all students enrolled in a course."""
    students = list(students_col.find(
        {"course_id": course_id},
        {"_id": 0}
    ))

    # If no real students yet, return demo data so the UI renders
    if not students:
        return [
            {"id": "student_001", "name": "Ali Hassan",
             "course_id": course_id, "mean_mastery": 0.45,
             "risk_score": 0.72, "days_since_login": 5},
            {"id": "student_002", "name": "Maya Tran",
             "course_id": course_id, "mean_mastery": 0.68,
             "risk_score": 0.31, "days_since_login": 1},
            {"id": "student_003", "name": "Omar Saleh",
             "course_id": course_id, "mean_mastery": 0.29,
             "risk_score": 0.85, "days_since_login": 9},
        ]
    return students


def get_student_summary(student_id: str, course_id: str) -> dict:
    """Return full analytics summary for one student."""
    student = students_col.find_one(
        {"id": student_id, "course_id": course_id},
        {"_id": 0}
    )

    # If no real data yet, return demo data
    if not student:
        return {
            "id":               student_id,
            "name":             "Demo Student",
            "course_id":        course_id,
            "mean_mastery":     0.42,
            "risk_score":       0.65,
            "days_since_login": 4,
            "recent_accuracy":  0.50,
            "topics": [
                {"topic": "Chapter 1 — Big-O notation",      "mastery": 0.82, "attempts": 12},
                {"topic": "Chapter 2 — Sorting algorithms",  "mastery": 0.71, "attempts": 9},
                {"topic": "Chapter 3 — Recursion",           "mastery": 0.55, "attempts": 7},
                {"topic": "Chapter 4 — Dynamic programming", "mastery": 0.31, "attempts": 5},
                {"topic": "Chapter 5 — Graph traversal",     "mastery": 0.22, "attempts": 3},
            ]
        }

    # Build topic list from mastery collection
    mastery_docs = list(mastery_col.find(
        {"student_id": student_id, "course_id": course_id},
        {"_id": 0}
    ))
    topics = [
        {
            "topic":    m["topic"],
            "mastery":  m.get("mastery", 0.15),
            "attempts": m.get("attempts", 0)
        }
        for m in mastery_docs
    ]

    return {
        "id":               student_id,
        "name":             student.get("name", "Unknown"),
        "course_id":        course_id,
        "mean_mastery":     student.get("mean_mastery", 0.15),
        "risk_score":       student.get("risk_score", 0.5),
        "days_since_login": student.get("days_since_login", 0),
        "recent_accuracy":  student.get("recent_accuracy", 0.5),
        "topics":           topics
    }


def upsert_student_mastery(student_id: str, course_id: str,
                           topic: str, mastery: float, attempts: int):
    """Update or insert mastery score for a student-topic pair."""
    mastery_col.update_one(
        {"student_id": student_id, "course_id": course_id, "topic": topic},
        {"$set": {
            "mastery":    mastery,
            "attempts":   attempts,
            "updated_at": datetime.now(timezone.utc)
        }},
        upsert=True
    )