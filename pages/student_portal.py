# portals/student_portal.py
import os
import streamlit as st
from agents.orchestrator  import classify_intent
from agents.tutor         import answer_question
from agents.assessment    import generate_quiz, generate_hint
from agents.analytics     import record_quiz_result
from database.courses     import get_courses, create_course, delete_course


def _make_course_id(name: str) -> str:
    """Convert a course name to a safe collection ID."""
    return name.strip().upper().replace(" ", "_")[:20]


def render_student_portal(student_id: str):
    """
    Entry point. Shows course selection or the active course portal
    depending on session state.
    """
    # ── Route: course selected → show portal ─────────────────
    if st.session_state.get("active_course_id"):
        _render_course_portal(student_id)
    else:
        _render_course_selection(student_id)


# ─────────────────────────────────────────────────────────────
# SCREEN 1 — Course selection
# ─────────────────────────────────────────────────────────────

def _render_course_selection(student_id: str):
    st.title("StudyMate")
    st.subheader("My Courses")

    courses = get_courses(student_id)

    # ── Existing courses ──────────────────────────────────────
    if courses:
        st.write("Select a course to continue:")
        st.write("")

        for course in courses:
            col_name, col_enter, col_del = st.columns([5, 2, 1])

            with col_name:
                st.markdown(
                    f"**{course['name']}**  "
                    f"<span style='color:grey;font-size:12px'>"
                    f"`{course['id']}`</span>",
                    unsafe_allow_html=True
                )

            with col_enter:
                if st.button(
                    "Open",
                    key=f"open_{course['id']}",
                    use_container_width=True
                ):
                    st.session_state.active_course_id   = course["id"]
                    st.session_state.active_course_name = course["name"]
                    # Clear any leftover quiz state from a previous session
                    for k in [
                        "quiz_questions", "quiz_current",
                        "quiz_score", "quiz_answers",
                        "quiz_done", "quiz_feedback",
                        "chat_history"
                    ]:
                        st.session_state.pop(k, None)
                    st.rerun()

            with col_del:
                if st.button(
                    "✕",
                    key=f"del_{course['id']}",
                    help="Remove course from your list"
                ):
                    delete_course(student_id, course["id"])
                    st.rerun()

        st.divider()

    else:
        st.info(
            "You have no courses yet. "
            "Create your first course below."
        )
        st.write("")

    # ── Create new course ─────────────────────────────────────
    st.write("**Create a new course:**")

    col_a, col_b = st.columns([4, 2])
    with col_a:
        new_name = st.text_input(
            "Course name",
            placeholder="e.g. Algorithms, Machine Learning...",
            key="new_course_name",
            label_visibility="collapsed"
        )
    with col_b:
        if st.button(
            "Create Course",
            use_container_width=True,
            key="create_course_btn"
        ):
            if not new_name.strip():
                st.error("Please enter a course name.")
            else:
                course_id = _make_course_id(new_name)
                result    = create_course(
                    student_id, new_name.strip(), course_id
                )
                if result is None:
                    st.error(
                        f"A course with ID '{course_id}' already "
                        f"exists. Choose a different name."
                    )
                else:
                    st.session_state.active_course_id   = course_id
                    st.session_state.active_course_name = new_name.strip()
                    for k in [
                        "quiz_questions", "quiz_current",
                        "quiz_score", "quiz_answers",
                        "quiz_done", "quiz_feedback",
                        "chat_history"
                    ]:
                        st.session_state.pop(k, None)
                    st.success(
                        f"Course '{new_name}' created!"
                    )
                    st.rerun()


# ─────────────────────────────────────────────────────────────
# SCREEN 2 — Active course portal
# ─────────────────────────────────────────────────────────────

def _render_course_portal(student_id: str):
    course_id   = st.session_state.active_course_id
    course_name = st.session_state.get(
        "active_course_name", course_id
    )

    # ── Top bar ───────────────────────────────────────────────
    col_back, col_title, col_switch = st.columns([1, 6, 2])

    with col_back:
        if st.button("← Courses", key="back_to_courses"):
            st.session_state.active_course_id   = None
            st.session_state.active_course_name = None
            st.rerun()

    with col_title:
        st.markdown(f"### {course_name}")
        st.caption(f"Course ID: `{course_id}`")

    with col_switch:
        courses = get_courses(student_id)
        other   = [
            c for c in courses
            if c["id"] != course_id
        ]
        if other:
            other_names = [c["name"] for c in other]
            chosen = st.selectbox(
                "Switch course",
                ["—"] + other_names,
                key="switch_course_select",
                label_visibility="collapsed"
            )
            if chosen != "—":
                target = next(
                    c for c in other
                    if c["name"] == chosen
                )
                st.session_state.active_course_id   = target["id"]
                st.session_state.active_course_name = target["name"]
                for k in [
                    "quiz_questions", "quiz_current",
                    "quiz_score", "quiz_answers",
                    "quiz_done", "quiz_feedback",
                    "chat_history"
                ]:
                    st.session_state.pop(k, None)
                st.rerun()

    st.divider()

    # ── Tabs ──────────────────────────────────────────────────
    tab_tutor, tab_quiz, tab_progress, tab_upload = st.tabs([
        "Tutor Chat", "Quiz",
        "My Progress", "Upload Materials"
    ])

    # ══════════════════════════════════════════════════════════
    # TUTOR TAB
    # ══════════════════════════════════════════════════════════
    with tab_tutor:
        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []

        for turn in st.session_state.chat_history:
            with st.chat_message("user"):
                st.write(turn["q"])
            with st.chat_message("assistant"):
                st.write(turn["a"])
                if turn.get("source") and \
                        turn.get("phase") == "explanation":
                    st.caption(turn["source"])

        question = st.chat_input(
            "Ask a question about your course..."
        )
        if question:
            with st.spinner("Thinking..."):
                result = answer_question(
                    course_id, question,
                    st.session_state.chat_history
                )
            with st.chat_message("user"):
                st.write(question)
            with st.chat_message("assistant"):
                st.write(result["answer"])
                phase = result.get("phase", "")
                if phase == "question":
                    st.caption("Guiding question")
                elif phase == "brief_explain":
                    st.caption("Hint + follow-up")
                elif phase == "hint":
                    st.caption("You're close — try again")
                elif phase == "explanation":
                    st.caption("Full explanation")
                    if result.get("source"):
                        st.caption(result["source"])
                elif phase == "redirect":
                    st.caption("Off-topic — redirected")
                elif phase == "fallback":
                    st.caption(
                        "Not found in course materials"
                    )
            st.session_state.chat_history.append({
                "q":      question,
                "a":      result["answer"],
                "source": result.get("source"),
                "phase":  result.get("phase")
            })

    # ══════════════════════════════════════════════════════════
    # QUIZ TAB
    # ══════════════════════════════════════════════════════════
    with tab_quiz:
        st.subheader("Quiz")

        from rag.retriever import get_chapters
        available_chapters = get_chapters(course_id)

        if not available_chapters:
            st.warning(
                "No course material found. "
                "Upload files in the Upload Materials tab first."
            )
        else:
            col1, col2, col3 = st.columns(3)
            with col1:
                chapter = st.selectbox(
                    "Chapter",
                    available_chapters,
                    key="quiz_chapter_select"
                )
            with col2:
                difficulty = st.selectbox(
                    "Difficulty",
                    ["easy", "medium", "hard"],
                    key="quiz_difficulty_select"
                )
            with col3:
                st.write("")
                st.write("")
                generate_btn = st.button(
                    "Generate 10 Questions",
                    use_container_width=True,
                    key="generate_quiz_btn"
                )

            if generate_btn:
                with st.spinner(
                    "Generating questions from "
                    "course material..."
                ):
                    questions = generate_quiz(
                        course_id, chapter, difficulty
                    )
                if not questions:
                    st.error(
                        "Could not generate questions. "
                        "Try uploading more material "
                        "for this chapter."
                    )
                else:
                    st.session_state.quiz_questions      = questions
                    st.session_state.quiz_current        = 0
                    st.session_state.quiz_score          = 0
                    st.session_state.quiz_answers        = []
                    st.session_state.quiz_done           = False
                    st.session_state.quiz_chapter_stored = chapter
                    st.session_state.quiz_feedback       = None
                    st.rerun()

            # ── Active quiz ───────────────────────────────────
            questions = st.session_state.get("quiz_questions", [])
            quiz_done = st.session_state.get("quiz_done", False)

            if questions and not quiz_done:
                current = st.session_state.get("quiz_current", 0)
                total   = len(questions)
                score   = st.session_state.get("quiz_score", 0)

                if current >= total:
                    st.session_state.quiz_done = True
                    st.rerun()

                q        = questions[current]
                feedback = st.session_state.get("quiz_feedback")

                st.progress(current / total)
                st.caption(
                    f"Question {current+1} of {total}  |  "
                    f"Score: {score}/{current}"
                )
                st.markdown(
                    f"**Q{current+1}. {q['question']}**"
                )
                st.write("")

                if not feedback:
                    chosen = st.radio(
                        "Choose your answer:",
                        [f"{k}:  {v}"
                         for k, v in q["options"].items()],
                        key="quiz_radio"
                    )
                    col_a, col_b = st.columns([2, 1])
                    with col_a:
                        if st.button("Submit Answer",
                                     key="quiz_submit"):
                            letter  = chosen[0]
                            correct = letter == q["answer"]
                            st.session_state.quiz_answers\
                                .append({
                                "question":   q["question"],
                                "chosen":     letter,
                                "correct":    q["answer"],
                                "is_correct": correct
                            })
                            st.session_state.quiz_feedback = {
                                "is_correct": correct,
                                "chosen":     letter,
                                "correct":    q["answer"],
                                "rationale":  q["rationale"],
                            }
                            if correct:
                                st.session_state.quiz_score\
                                    += 1
                                mastery = st.session_state\
                                    .get(
                                    f"mastery_{chapter}",
                                    0.15
                                )
                                new_m = record_quiz_result(
                                    student_id, course_id,
                                    chapter, True, mastery
                                )
                                st.session_state[
                                    f"mastery_{chapter}"
                                ] = new_m
                            else:
                                record_quiz_result(
                                    student_id, course_id,
                                    chapter, False,
                                    st.session_state.get(
                                        f"mastery_{chapter}",
                                        0.15
                                    )
                                )
                            st.rerun()
                    with col_b:
                        if st.button("Skip", key="quiz_skip"):
                            st.session_state.quiz_answers\
                                .append({
                                "question":   q["question"],
                                "chosen":     "skipped",
                                "correct":    q["answer"],
                                "is_correct": False
                            })
                            st.session_state.quiz_feedback\
                                = None
                            nxt = current + 1
                            if nxt < total:
                                st.session_state\
                                    .quiz_current = nxt
                            else:
                                st.session_state\
                                    .quiz_done = True
                            st.rerun()
                else:
                    if feedback["is_correct"]:
                        st.success(
                            f"Correct!  "
                            f"{feedback['rationale']}"
                        )
                    else:
                        st.error(
                            f"Wrong answer.  Correct: "
                            f"**{feedback['correct']}**\n\n"
                            f"{feedback['rationale']}"
                        )
                    if st.button("Next Question →",
                                 key="quiz_next"):
                        st.session_state.quiz_feedback = None
                        nxt = current + 1
                        if nxt < total:
                            st.session_state.quiz_current\
                                = nxt
                        else:
                            st.session_state.quiz_done\
                                = True
                        st.rerun()

            elif quiz_done and questions:
                total   = len(questions)
                score   = st.session_state.get(
                    "quiz_score", 0
                )
                answers = st.session_state.get(
                    "quiz_answers", []
                )
                pct     = round(
                    (score / total) * 100
                ) if total else 0

                st.divider()
                st.subheader("Quiz complete!")
                c1, c2, c3 = st.columns(3)
                c1.metric("Score",   f"{score}/{total}")
                c2.metric("Percent", f"{pct}%")
                c3.metric(
                    "Chapter",
                    st.session_state.get(
                        "quiz_chapter_stored", ""
                    )
                )
                if pct >= 80:
                    st.success("Excellent mastery!")
                elif pct >= 50:
                    st.warning(
                        "Good effort. Review missed topics."
                    )
                else:
                    st.error(
                        "Keep studying. Use Tutor Chat "
                        "to review weak areas."
                    )

                st.divider()
                st.write("**Answer review:**")
                for i, ans in enumerate(answers):
                    icon = "✅" if ans["is_correct"] else "❌"
                    with st.expander(
                        f"{icon} Q{i+1}: "
                        f"{ans['question'][:60]}..."
                    ):
                        st.write(
                            f"Your answer: **{ans['chosen']}**"
                        )
                        if not ans["is_correct"]:
                            st.write(
                                f"Correct: "
                                f"**{ans['correct']}**"
                            )

                if st.button("Retake Quiz",
                             key="retake_quiz"):
                    for k in [
                        "quiz_questions", "quiz_current",
                        "quiz_score", "quiz_answers",
                        "quiz_done", "quiz_feedback"
                    ]:
                        st.session_state.pop(k, None)
                    st.rerun()

    # ══════════════════════════════════════════════════════════
    # PROGRESS TAB
    # ══════════════════════════════════════════════════════════
    with tab_progress:
        st.subheader("Your Mastery Map")
        from rag.retriever import get_chapters
        chapters = get_chapters(course_id)

        if not chapters:
            st.info(
                "Upload course materials to see "
                "your progress."
            )
        else:
            for ch in chapters:
                mastery = st.session_state.get(
                    f"mastery_{ch}", 0.15
                )
                color = (
                    "🟢" if mastery >= 0.80 else
                    "🟡" if mastery >= 0.50 else
                    "🔴"
                )
                ca, cb, cc = st.columns([3, 5, 2])
                with ca:
                    st.write(f"{color} {ch}")
                with cb:
                    st.progress(mastery)
                with cc:
                    st.write(f"{mastery:.0%}")

    # ══════════════════════════════════════════════════════════
    # UPLOAD TAB
    # ══════════════════════════════════════════════════════════
    with tab_upload:
        st.subheader("Upload course materials")
        st.caption(
            "Supported: PDF, PPTX, DOCX, TXT · "
            "Images: PNG, JPG · Audio: MP3, WAV, MP4"
        )

        from rag.retriever import get_chapters
        existing_chapters = get_chapters(course_id)

        st.write("**Assign to chapter:**")
        col_sel, col_new = st.columns([3, 2])

        with col_sel:
            chapter_opts = (
                existing_chapters
                if existing_chapters
                else ["Chapter 1"]
            )
            selected_chapter = st.selectbox(
                "Existing chapters",
                chapter_opts,
                key="upload_existing_chapter"
            )

        with col_new:
            new_chapter = st.text_input(
                "Or create new chapter",
                placeholder="e.g. Chapter 8",
                key="upload_new_chapter"
            )

        chapter = (
            new_chapter.strip()
            if new_chapter.strip()
            else selected_chapter
        )
        st.caption(
            f"Files will be assigned to: **{chapter}**"
        )

        uploaded_files = st.file_uploader(
            "Drop files here or click to browse",
            type=[
                "pdf", "pptx", "docx", "txt",
                "png", "jpg", "jpeg",
                "mp3", "wav", "mp4"
            ],
            accept_multiple_files=True,
            key="student_file_uploader"
        )

        if uploaded_files:
            for f in uploaded_files:
                st.write(
                    f"  - {f.name} "
                    f"({round(f.size/1024, 1)} KB)"
                )

        if st.button(
            "Process & Index into Qdrant",
            disabled=not uploaded_files,
            key="student_upload_btn"
        ):
            import tempfile
            from rag.ingest_file import ingest_file

            total_chunks  = 0
            success_count = 0
            fail_count    = 0

            for uploaded_file in uploaded_files:
                st.markdown(
                    f"**Processing: "
                    f"{uploaded_file.name}**"
                )
                suffix = os.path.splitext(
                    uploaded_file.name
                )[1]
                with tempfile.NamedTemporaryFile(
                        delete=False,
                        suffix=suffix) as tmp:
                    tmp.write(uploaded_file.getbuffer())
                    tmp_path = tmp.name

                with st.spinner(
                    f"Embedding {uploaded_file.name}..."
                ):
                    result = ingest_file(
                        file_path=tmp_path,
                        course_id=course_id,
                        chapter=chapter,
                        filename=uploaded_file.name
                    )
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

                if result["success"]:
                    st.success(
                        f"{uploaded_file.name} — "
                        f"{result['chunks']} chunks → "
                        f"**{chapter}**"
                    )
                    total_chunks  += result["chunks"]
                    success_count += 1
                else:
                    st.error(
                        f"{uploaded_file.name} — "
                        f"Failed: {result['error']}"
                    )
                    fail_count += 1

            if success_count > 0:
                st.success(
                    f"Done — {total_chunks} chunks indexed."
                )
                st.rerun()

            if fail_count > 0:
                st.error(
                    f"{fail_count} file(s) failed."
                )

        st.divider()
        st.write("**Chapters in this course:**")
        current_chapters = get_chapters(course_id)
        if current_chapters:
            for ch in current_chapters:
                st.write(f"  - {ch}")
        else:
            st.caption(
                "No chapters yet — upload files above."
            )