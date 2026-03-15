# app.py
import streamlit as st
from pages.student_portal       import render_student_portal
from portals.learning_style_quiz  import render_learning_style_quiz
from database.learning_style      import get_style

st.set_page_config(
    page_title="Elyssa",
    page_icon="",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ── Not logged in → landing page ──────────────────────────────
if "role" not in st.session_state:
    st.title("Elyssa")
    st.subheader(
        "The AI tutor that asks better questions "
        "to build better thinkers"
    )
    st.write(
        "Great thinkers weren't born, they were questioned. "
        "Elyssa is the tutor that believes you already know — "
        "you just haven't been asked the right questions yet."
    )
    st.write("")

    col1, col2, col3 = st.columns([2, 2, 2])
    with col2:
        if st.button(
            "Start Learning",
            use_container_width=True,
            key="login_student"
        ):
            st.session_state.role               = "student"
            st.session_state.student_id         = "student_001"
            st.session_state.active_course_id   = None
            st.session_state.active_course_name = None
            st.rerun()

# ── Logged in → check if learning style quiz needed ───────────
elif st.session_state.role == "student":
    student_id = st.session_state.student_id

    # Check if style already saved from a previous session
    saved_style = get_style(student_id)
    if saved_style:
        st.session_state.learning_style      = saved_style
        st.session_state.learning_style_done = True

    style_done = st.session_state.get(
        "learning_style_done", False
    )

    if not style_done:
        # Show learning style quiz before portal
        render_learning_style_quiz(student_id)
    else:
        # Style complete — show course portal
        render_student_portal(student_id)