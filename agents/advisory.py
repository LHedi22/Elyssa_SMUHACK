# agents/advisory.py
from database.mongo_client import get_student_summary
from agents.supervision import check_grounding
from models.model_loader import call_llm
import config

ADVISORY_SYSTEM = """You are a professor advisory assistant.
Analyse student performance data and give concise, actionable insights.
Only state facts that are directly present in the data provided.
Be specific — mention exact topics, scores, and trends.
"""

def advise_on_student(student_id: str, course_id: str,
                      professor_question: str) -> str:
    # Fetch structured student data from MongoDB
    data = get_student_summary(student_id, course_id)
    if not data:
        return f"No data found for student {student_id} in course {course_id}."

    data_text = f"""
Student: {data['name']}
Course: {course_id}
Overall mastery: {data['mean_mastery']:.0%}
Risk score: {data['risk_score']:.2f}
Days since last login: {data['days_since_login']}
Topic breakdown:
{chr(10).join([f"  - {t['topic']}: {t['mastery']:.0%} ({t['attempts']} attempts)" for t in data['topics']])}
Recent quiz performance: {data['recent_accuracy']:.0%} accuracy over last 10 questions
"""

    user_prompt = f"""Student performance data:
{data_text}

Professor's question: {professor_question}"""

    return call_llm(config.ADVISORY_MODEL, ADVISORY_SYSTEM,
                    user_prompt, temperature=0.2)