# agents/suggestions.py
from datetime import datetime, timezone, timedelta
from collections import Counter, defaultdict
from database.mongo_client import (
    get_mastery,
    get_quiz_history,
    get_tutor_history,
    get_last_interaction,
    get_last_interaction_per_topic,
    get_session_dates,
    get_fallback_count
)
from agents.analytics import compute_risk_score


# ── Priority levels ───────────────────────────────────────────
CRITICAL = "critical"   # Red  — act now
WARNING  = "warning"    # Amber — act soon
INFO     = "info"       # Blue — good to know
SUCCESS  = "success"    # Green — positive feedback


def _days_since(dt: datetime) -> int:
    if dt is None:
        return 999
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (now - dt).days


def _mastery_trend(quiz_history: list,
                   topic: str,
                   window: int = 5) -> float:
    """
    Returns slope of mastery over last N quiz attempts
    on a topic. Positive = improving, negative = declining.
    """
    events = [
        e for e in quiz_history
        if e.get("topic") == topic
    ][-window:]

    if len(events) < 2:
        return 0.0

    scores = [e.get("new_mastery", 0.15) for e in events]
    n      = len(scores)
    x_mean = (n - 1) / 2
    y_mean = sum(scores) / n
    num    = sum((i - x_mean) * (scores[i] - y_mean)
                 for i in range(n))
    den    = sum((i - x_mean) ** 2 for i in range(n))
    return round(num / den, 4) if den != 0 else 0.0


def generate_suggestions(student_id: str,
                          course_id: str,
                          chapters: list[str],
                          exam_days: int = None) -> list[dict]:
    """
    Main entry point. Analyses all student data and
    returns a ranked list of suggestion dicts:
    {
        "priority":    "critical" | "warning" | "info" | "success",
        "category":    str,
        "title":       str,
        "body":        str,
        "action":      str | None,   # button label
        "action_data": dict | None   # passed back to portal
    }
    """
    suggestions = []

    # ── Load all data ─────────────────────────────────────────
    mastery_data    = get_mastery(student_id, course_id)
    quiz_history    = get_quiz_history(student_id, course_id)
    tutor_history   = get_tutor_history(student_id, course_id)
    last_seen       = get_last_interaction(student_id, course_id)
    topic_last_seen = get_last_interaction_per_topic(
        student_id, course_id
    )
    session_dates   = get_session_dates(student_id, course_id)
    fallback_count  = get_fallback_count(student_id, course_id)
    days_inactive   = _days_since(last_seen)

    mastery_scores  = [
        mastery_data.get(ch, 0.15) for ch in chapters
    ]
    mastery_trend   = (
        (mastery_scores[-1] - mastery_scores[0])
        if len(mastery_scores) >= 2 else 0.0
    )

    # ── 1. ENGAGEMENT ALERTS ──────────────────────────────────

    if days_inactive >= 7:
        suggestions.append({
            "priority": CRITICAL,
            "category": "Engagement",
            "title":    f"You haven't studied in {days_inactive} days",
            "body":     "Long gaps between sessions cause mastery to "
                        "decay. Even a 10-minute quiz session helps "
                        "retain what you've learned.",
            "action":   "Start a quick quiz",
            "action_data": {"tab": "quiz"}
        })
    elif days_inactive >= 3:
        suggestions.append({
            "priority": WARNING,
            "category": "Engagement",
            "title":    f"{days_inactive} days since your last session",
            "body":     "You're at risk of forgetting recent progress. "
                        "A short tutor session or quiz will keep "
                        "you on track.",
            "action":   "Resume studying",
            "action_data": {"tab": "tutor"}
        })

    # ── 2. RISK SCORE ─────────────────────────────────────────

    quiz_rate = (
        len(quiz_history) / 14.0
        if quiz_history else 0.0
    )
    risk = compute_risk_score(
        mastery_scores,
        days_since_login=days_inactive,
        quiz_attempt_rate=min(quiz_rate, 1.0),
        mastery_trend=mastery_trend
    )

    if risk >= 0.75:
        suggestions.append({
            "priority": CRITICAL,
            "category": "Risk",
            "title":    "High risk of falling behind",
            "body":     f"Your risk score is {risk:.0%}. Low mastery "
                        "combined with low engagement puts you at "
                        "risk. Focus on your red topics immediately.",
            "action":   None,
            "action_data": None
        })
    elif risk >= 0.50:
        suggestions.append({
            "priority": WARNING,
            "category": "Risk",
            "title":    "Moderate risk detected",
            "body":     f"Your risk score is {risk:.0%}. Increasing "
                        "your quiz frequency and tutor sessions "
                        "this week will reduce it.",
            "action":   None,
            "action_data": None
        })

    # ── 3. MASTERY-BASED SUGGESTIONS ─────────────────────────

    red_chapters    = []
    yellow_chapters = []
    green_chapters  = []
    untouched       = []

    for ch in chapters:
        score = mastery_data.get(ch, 0.15)
        if ch not in mastery_data:
            untouched.append(ch)
        elif score < 0.50:
            red_chapters.append((ch, score))
        elif score < 0.80:
            yellow_chapters.append((ch, score))
        else:
            green_chapters.append((ch, score))

    # Weakest topic
    if red_chapters:
        worst_ch, worst_score = min(
            red_chapters, key=lambda x: x[1]
        )
        suggestions.append({
            "priority": CRITICAL,
            "category": "Knowledge Gap",
            "title":    f"Critical gap: {worst_ch} ({worst_score:.0%})",
            "body":     f"{worst_ch} is your weakest topic. "
                        "Start with the tutor to understand the "
                        "fundamentals, then take a quiz to test "
                        "your understanding.",
            "action":   f"Study {worst_ch}",
            "action_data": {
                "tab":     "tutor",
                "message": f"Explain {worst_ch} to me"
            }
        })

    # Almost mastered topics — quick win
    for ch, score in yellow_chapters:
        if score >= 0.70:
            suggestions.append({
                "priority": INFO,
                "category": "Quick Win",
                "title":    f"Almost mastered: {ch} ({score:.0%})",
                "body":     f"You are close to mastering {ch}. "
                            "One quiz session should push you "
                            "over 80%.",
                "action":   f"Quiz on {ch}",
                "action_data": {
                    "tab":        "quiz",
                    "chapter":    ch,
                    "difficulty": "medium"
                }
            })

    # Untouched chapters
    for ch in untouched[:2]:  # Max 2 untouched alerts
        suggestions.append({
            "priority": WARNING,
            "category": "Coverage",
            "title":    f"You haven't started {ch} yet",
            "body":     f"{ch} has course material uploaded but "
                        "you haven't interacted with it. Start "
                        "with the tutor to get an overview.",
            "action":   f"Explore {ch}",
            "action_data": {
                "tab":     "tutor",
                "message": f"Give me an overview of {ch}"
            }
        })

    # Mastered topics — positive feedback
    if green_chapters:
        ch_names = ", ".join(
            ch for ch, _ in green_chapters
        )
        suggestions.append({
            "priority": SUCCESS,
            "category": "Achievement",
            "title":    f"Strong mastery on "
                        f"{len(green_chapters)} topic(s)",
            "body":     f"Well done on: {ch_names}. "
                        "Try Hard difficulty quizzes on these "
                        "topics to challenge yourself further.",
            "action":   None,
            "action_data": None
        })

    # ── 4. QUIZ PERFORMANCE PATTERNS ─────────────────────────

    if quiz_history:
        # Wrong answer streaks per topic
        topic_wrong = defaultdict(int)
        for e in quiz_history[:20]:
            if not e.get("correct", True):
                topic_wrong[e.get("topic", "")] += 1

        for topic, wrong_count in topic_wrong.items():
            if wrong_count >= 3:
                suggestions.append({
                    "priority": WARNING,
                    "category": "Quiz Pattern",
                    "title":    f"{wrong_count} wrong answers in a "
                                f"row on {topic}",
                    "body":     "Repeated quiz failures suggest a "
                                "conceptual gap. Use the tutor to "
                                "understand the concept before "
                                "retaking the quiz.",
                    "action":   "Ask the tutor",
                    "action_data": {
                        "tab":     "tutor",
                        "message": f"I keep getting {topic} wrong, "
                                   "can you help me understand it?"
                    }
                })

        # Skipped topics pattern
        skipped = [
            e for e in quiz_history
            if e.get("chosen") == "skipped"
        ]
        skipped_topics = Counter(
            e.get("topic", "") for e in skipped
        )
        for topic, count in skipped_topics.items():
            if count >= 3:
                suggestions.append({
                    "priority": WARNING,
                    "category": "Quiz Pattern",
                    "title":    f"You keep skipping {topic}",
                    "body":     f"You've skipped {topic} questions "
                                f"{count} times. This topic likely "
                                "needs attention — start with an "
                                "easy difficulty quiz.",
                    "action":   f"Try easy quiz on {topic}",
                    "action_data": {
                        "tab":        "quiz",
                        "chapter":    topic,
                        "difficulty": "easy"
                    }
                })

    # ── 5. SPACED REPETITION ──────────────────────────────────

    for ch in chapters:
        last_dt = topic_last_seen.get(ch)
        if last_dt is None:
            continue
        days_ago = _days_since(last_dt)
        score    = mastery_data.get(ch, 0.15)

        # Only suggest review for topics previously learned
        if score >= 0.50 and days_ago >= 7:
            suggestions.append({
                "priority": INFO,
                "category": "Spaced Repetition",
                "title":    f"Review due: {ch}",
                "body":     f"You last studied {ch} {days_ago} days "
                            "ago. A quick review prevents forgetting "
                            "and strengthens long-term retention.",
                "action":   f"Review {ch}",
                "action_data": {
                    "tab":        "quiz",
                    "chapter":    ch,
                    "difficulty": "easy"
                }
            })

    # ── 6. TUTOR INTERACTION PATTERNS ────────────────────────

    if tutor_history:
        # Count fallbacks this week
        if fallback_count >= 3:
            suggestions.append({
                "priority": WARNING,
                "category": "Content Gap",
                "title":    f"Tutor couldn't answer "
                            f"{fallback_count} questions this week",
                "body":     "Several of your questions weren't "
                            "covered in your uploaded materials. "
                            "Upload more lecture notes to improve "
                            "tutor quality.",
                "action":   "Upload more materials",
                "action_data": {"tab": "upload"}
            })

        # Repeated questions on same topic
        recent_topics = [
            e.get("topic", "")
            for e in tutor_history[:15]
        ]
        topic_counts = Counter(recent_topics)
        for topic, count in topic_counts.items():
            if count >= 5 and topic:
                score = mastery_data.get(topic, 0.15)
                if score < 0.60:
                    suggestions.append({
                        "priority": WARNING,
                        "category": "Tutor Pattern",
                        "title":    f"Asking a lot about {topic} "
                                    f"but mastery is still low",
                        "body":     f"You've asked {count} questions "
                                    f"about {topic} but your mastery "
                                    "hasn't improved much. Try taking "
                                    "a quiz to actively test yourself "
                                    "instead of just asking.",
                        "action":   f"Quiz on {topic}",
                        "action_data": {
                            "tab":     "quiz",
                            "chapter": topic
                        }
                    })

    # ── 7. EXAM PROXIMITY ─────────────────────────────────────

    if exam_days is not None:
        weak = [ch for ch in chapters
                if mastery_data.get(ch, 0.15) < 0.50]

        if exam_days <= 3 and weak:
            suggestions.append({
                "priority": CRITICAL,
                "category": "Exam Alert",
                "title":    f"Exam in {exam_days} days — "
                            f"{len(weak)} chapters below 50%",
                "body":     f"Critical topics: "
                            f"{', '.join(weak[:3])}. "
                            "Focus all remaining time on these.",
                "action":   None,
                "action_data": None
            })
        elif exam_days <= 7 and weak:
            suggestions.append({
                "priority": WARNING,
                "category": "Exam Alert",
                "title":    f"Exam in {exam_days} days — "
                            f"plan your study",
                "body":     f"You have {len(weak)} chapters that "
                            "need work. Suggested order: "
                            f"{', '.join(weak)}.",
                "action":   None,
                "action_data": None
            })

    # ── 8. POSITIVE STREAKS ───────────────────────────────────

    if len(session_dates) >= 3:
        # Check if last 3 sessions were on consecutive days
        if len(session_dates) >= 3:
            dates_only = [
                d.date() if d.tzinfo is None
                else d.astimezone(
                    timezone.utc
                ).date()
                for d in session_dates[:3]
            ]
            diffs = [
                abs((dates_only[i] - dates_only[i+1]).days)
                for i in range(2)
            ]
            if all(d <= 1 for d in diffs):
                suggestions.append({
                    "priority": SUCCESS,
                    "category": "Streak",
                    "title":    "3-day study streak!",
                    "body":     "Consistent daily practice is the "
                                "most effective way to retain "
                                "knowledge. Keep it up.",
                    "action":   None,
                    "action_data": None
                })

    # ── 9. STUDY PLAN (if enough data) ───────────────────────

    if len(chapters) >= 3 and mastery_data:
        plan = _build_study_plan(
            chapters, mastery_data, exam_days
        )
        if plan:
            suggestions.append({
                "priority": INFO,
                "category": "Study Plan",
                "title":    "Recommended study order",
                "body":     plan,
                "action":   None,
                "action_data": None
            })

    # ── Sort: critical first, then warning, info, success ────
    order = {CRITICAL: 0, WARNING: 1, INFO: 2, SUCCESS: 3}
    suggestions.sort(
        key=lambda x: order.get(x["priority"], 99)
    )

    return suggestions


def _build_study_plan(chapters: list[str],
                      mastery_data: dict,
                      exam_days: int = None) -> str:
    """Build a plain-text prioritised study plan."""
    scored = [
        (ch, mastery_data.get(ch, 0.15))
        for ch in chapters
    ]

    # Sort: weakest first, then medium, then strong
    red    = [(c, s) for c, s in scored if s < 0.50]
    yellow = [(c, s) for c, s in scored if 0.50 <= s < 0.80]
    green  = [(c, s) for c, s in scored if s >= 0.80]

    red.sort(key=lambda x: x[1])
    yellow.sort(key=lambda x: x[1])

    plan_parts = []
    if red:
        names = ", ".join(c for c, _ in red)
        plan_parts.append(f"Priority 1 (critical): {names}")
    if yellow:
        names = ", ".join(c for c, _ in yellow)
        plan_parts.append(f"Priority 2 (reinforce): {names}")
    if green:
        names = ", ".join(c for c, _ in green)
        plan_parts.append(f"Priority 3 (maintain): {names}")

    if exam_days:
        plan_parts.append(
            f"Time available: {exam_days} days"
        )

    return "\n".join(plan_parts) if plan_parts else ""