# portals/learning_style_quiz.py
import streamlit as st
from database.learning_style import (
    QUESTIONS, STYLE_DESCRIPTIONS,
    score_quiz, save_style
)


def render_learning_style_quiz(student_id: str):
    """
    Full-screen learning style quiz.
    Sets st.session_state.learning_style_done = True when complete.
    """

    # ── Header ────────────────────────────────────────────────
    st.title("Elyssa")
    st.subheader("Before we begin — how do you learn best?")
    st.caption(
        "10 quick questions. Choose the option that "
        "best describes you. This helps Elyssa adapt "
        "to your learning style."
    )
    st.progress(
        st.session_state.get("quiz_q_index", 0) / 10
    )
    st.write("")

    # ── One question at a time ────────────────────────────────
    idx = st.session_state.get("quiz_q_index", 0)

    if idx < len(QUESTIONS):
        q = QUESTIONS[idx]

        st.markdown(
            f"**Question {idx + 1} of {len(QUESTIONS)}**"
        )
        st.markdown(f"### {q['q']}")
        st.write("")

        chosen = st.radio(
            "Your answer:",
            options=list(q["options"].keys()),
            format_func=lambda k: f"{k}.  {q['options'][k]}",
            key=f"ls_q_{idx}",
            label_visibility="collapsed"
        )

        st.write("")
        col1, col2 = st.columns([1, 5])
        with col1:
            if st.button(
                "Next →",
                key=f"ls_next_{idx}",
                use_container_width=True
            ):
                # Save this answer
                if "ls_answers" not in st.session_state:
                    st.session_state.ls_answers = {}
                st.session_state.ls_answers[idx] = chosen
                st.session_state.quiz_q_index    = idx + 1
                st.rerun()

        # Back button (except on first question)
        if idx > 0:
            with col2:
                if st.button(
                    "← Back",
                    key=f"ls_back_{idx}"
                ):
                    st.session_state.quiz_q_index = idx - 1
                    st.rerun()

    # ── All questions answered — show results ─────────────────
    else:
        answers = st.session_state.get("ls_answers", {})
        result  = score_quiz(answers)
        dominant = result["dominant"]
        info    = STYLE_DESCRIPTIONS[dominant]

        # Save to disk
        save_style(student_id, result)
        st.session_state.learning_style = result

        # ── Results screen ────────────────────────────────────
        st.markdown(f"## {info['emoji']}  You are a "
                    f"**{dominant} Learner**")
        st.markdown(f"*{info['tagline']}*")
        st.write("")

        # Score breakdown
        st.write("**Your scores:**")
        styles_ordered = sorted(
            ["Visual", "Auditory",
             "Reading/Writing", "Kinesthetic"],
            key=lambda s: result[s],
            reverse=True
        )
        for s in styles_ordered:
            score = result[s]
            bar   = score / 10
            col_a, col_b, col_c = st.columns([3, 5, 1])
            with col_a:
                marker = " ← dominant" if s == dominant else ""
                st.write(f"**{s}**{marker}")
            with col_b:
                st.progress(bar)
            with col_c:
                st.write(f"{score}/10")

        st.divider()

        # What this means
        st.write("**How you learn best:**")
        for item in info["best_with"]:
            st.write(f"  - {item}")

        st.write("")
        st.info(f"**How Elyssa will adapt for you:**\n\n"
                f"{info['tutor_adapt']}")

        st.write("")
        if st.button(
            "Start learning →",
            key="ls_finish_btn",
            use_container_width=False
        ):
            # Clean up quiz session state
            st.session_state.learning_style_done = True
            st.session_state.pop("quiz_q_index", None)
            st.session_state.pop("ls_answers",   None)
            st.rerun()