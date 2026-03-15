# app.py
import streamlit as st
from pages.student_portal  import render_student_portal
from pages.professor_portal import render_professor_portal

st.set_page_config(
    page_title="StudyMate",
    page_icon="",
    layout="wide"
)

if "role" not in st.session_state:
    st.title("StudyMate")
    st.write("")
    col1, col2 = st.columns(2)
    with col1:
        if st.button(
            "I am a Student",
            use_container_width=True,
            key="login_student"
        ):
            st.session_state.role       = "student"
            st.session_state.student_id = "student_001"
            st.session_state.active_course_id   = None
            st.session_state.active_course_name = None
            st.rerun()
    with col2:
        if st.button(
            "I am a Professor",
            use_container_width=True,
            key="login_professor"
        ):
            st.session_state.role      = "professor"
            st.session_state.course_id = "CS301"
            st.rerun()

elif st.session_state.role == "student":
    render_student_portal(st.session_state.student_id)

elif st.session_state.role == "professor":
    render_professor_portal(st.session_state.course_id)