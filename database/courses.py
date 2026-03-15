# database/courses.py
# Stores courses as a simple JSON file — no extra DB needed.

import json
import os

COURSES_FILE = "data/courses.json"


def _load() -> dict:
    if not os.path.exists(COURSES_FILE):
        os.makedirs("data", exist_ok=True)
        return {}
    with open(COURSES_FILE, "r") as f:
        return json.load(f)


def _save(data: dict):
    os.makedirs("data", exist_ok=True)
    with open(COURSES_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_courses(student_id: str) -> list[dict]:
    """Return all courses for a student."""
    data = _load()
    return data.get(student_id, [])


def create_course(student_id: str,
                  course_name: str,
                  course_id: str) -> dict:
    """Create a new course for a student."""
    data   = _load()
    course = {
        "id":   course_id,
        "name": course_name
    }
    if student_id not in data:
        data[student_id] = []

    # Prevent duplicate IDs
    existing_ids = [c["id"] for c in data[student_id]]
    if course_id in existing_ids:
        return None

    data[student_id].append(course)
    _save(data)
    return course


def delete_course(student_id: str, course_id: str):
    """Remove a course from a student's list."""
    data = _load()
    if student_id in data:
        data[student_id] = [
            c for c in data[student_id]
            if c["id"] != course_id
        ]
        _save(data)