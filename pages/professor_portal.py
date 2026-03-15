# pages/professor_portal.py
import os
import streamlit as st
from rag.ingestion_pipeline import parse_document, chunk_text, extract_concepts
from rag.retriever import create_collection, upsert_chunks
from agents.advisory import advise_on_student
from database.mongo_client import get_all_students, get_student_summary
import os, tempfile

def render_professor_portal(course_id: str):
    st.title("StudyMate — Professor Portal")

    tab_upload, tab_analytics, tab_student, tab_chat = st.tabs(
        ["Upload Materials", "Class Analytics",
         "Student Details", "Advisory Chatbot"]
    )

    # ── UPLOAD TAB ────────────────────────────────────────────
    with tab_upload:
        st.subheader("Upload course materials")
        st.caption("Supported: PDF, PPTX, DOCX, TXT, PNG, JPG, MP3, WAV, MP4")

        chapter = st.selectbox(
            "Assign files to chapter",
            [f"Chapter {i}" for i in range(1, 11)],
            key="upload_chapter"
        )

        uploaded_files = st.file_uploader(
            "Drop files here or click to browse",
            type=[
                "pdf", "pptx", "docx", "txt", "doc",
                "png", "jpg", "jpeg", "tiff",
                "mp3", "wav", "mp4", "m4a"
            ],
            accept_multiple_files=True,
            key="file_uploader"
        )

        if uploaded_files:
            st.write(f"{len(uploaded_files)} file(s) selected:")
            for f in uploaded_files:
                st.write(f"  - {f.name} ({round(f.size / 1024, 1)} KB)")

        if st.button(
            "Process & Index into Qdrant",
            disabled=not uploaded_files
        ):
            import tempfile
            from rag.ingest_file import ingest_file

            total_chunks  = 0
            success_count = 0
            fail_count    = 0

            for uploaded_file in uploaded_files:
                st.markdown(f"**Processing: {uploaded_file.name}**")

                # ── Write file to disk correctly ──────────────
                suffix = os.path.splitext(uploaded_file.name)[1]

                with tempfile.NamedTemporaryFile(
                        delete=False,
                        suffix=suffix) as tmp:
                    tmp.write(uploaded_file.getbuffer())  # ← getbuffer not read
                    tmp_path = tmp.name

                st.write(f"Temp file written to: `{tmp_path}`")
                st.write(f"File size on disk: "
                         f"{os.path.getsize(tmp_path)} bytes")

                # ── Run the full ingest pipeline ──────────────
                with st.spinner(
                        f"Parsing and embedding "
                        f"{uploaded_file.name}..."):
                    result = ingest_file(
                        file_path=tmp_path,
                        course_id=course_id,
                        chapter=chapter,
                        filename=uploaded_file.name
                    )

                # ── Clean up temp file ────────────────────────
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

                # ── Show result ───────────────────────────────
                if result["success"]:
                    st.success(
                        f"{uploaded_file.name} — "
                        f"{result['chunks']} chunks indexed "
                        f"into {result['chapter']}"
                    )
                    total_chunks  += result["chunks"]
                    success_count += 1
                else:
                    st.error(
                        f"{uploaded_file.name} — "
                        f"Failed: {result['error']}"
                    )
                    fail_count += 1

            # ── Final summary ─────────────────────────────────
            st.divider()
            if success_count > 0:
                st.success(
                    f"Done — {success_count} file(s) indexed, "
                    f"{total_chunks} total chunks in Qdrant"
                )

                # Auto-refresh collection stats
                from qdrant_client import QdrantClient
                import config as cfg
                try:
                    q    = QdrantClient(
                        host=cfg.QDRANT_HOST,
                        port=cfg.QDRANT_PORT
                    )
                    info = q.get_collection(course_id)
                    st.info(
                        f"Collection '{course_id}' now has "
                        f"**{info.points_count} total chunks** "
                        f"stored in Qdrant"
                    )
                except Exception:
                    pass

            if fail_count > 0:
                st.error(
                    f"{fail_count} file(s) failed — "
                    f"check errors above"
                )

        # ── Show what's already in Qdrant ─────────────────────
        st.divider()
        st.subheader("Current collection contents")

        if st.button("Refresh collection stats"):
            from qdrant_client import QdrantClient
            import config as cfg

            qdrant = QdrantClient(
                host=cfg.QDRANT_HOST, port=cfg.QDRANT_PORT)
            existing = [
                c.name for c in qdrant.get_collections().collections
            ]

            if course_id not in existing:
                st.warning(
                    f"Collection '{course_id}' does not exist yet. "
                    "Upload files to create it."
                )
            else:
                info = qdrant.get_collection(course_id)
                st.metric("Total chunks stored", info.points_count)
                st.metric("Vector dimensions",
                          info.config.params.vectors.size)

                # Show breakdown by chapter
                if info.points_count > 0:
                    all_points = qdrant.scroll(
                        collection_name=course_id,
                        limit=2000,
                        with_payload=True,
                        with_vectors=False
                    )[0]

                    from collections import Counter
                    chapters = Counter(
                        p.payload.get("chapter", "Unknown")
                        for p in all_points
                    )
                    st.write("Chunks per chapter:")
                    for ch, count in sorted(chapters.items()):
                        st.write(f"  - {ch}: {count} chunks")

    # ── CLASS ANALYTICS TAB ───────────────────────────────────
    with tab_analytics:
        st.subheader("Class Overview")
        students = get_all_students(course_id)
        if not students:
            st.info("No student data yet.")
        else:
            col1, col2, col3 = st.columns(3)
            masteries = [s["mean_mastery"] for s in students]
            at_risk   = sum(1 for s in students if s["risk_score"] > 0.7)

            col1.metric("Students", len(students))
            col2.metric("Avg Mastery", f"{sum(masteries)/len(masteries):.0%}")
            col3.metric("At Risk", at_risk)

            st.divider()
            for s in students:
                risk_color = (
                    "🔴" if s["risk_score"] > 0.7 else
                    "🟡" if s["risk_score"] > 0.4 else "🟢"
                )
                st.write(
                    f"{risk_color} **{s['name']}** — "
                    f"Mastery: {s['mean_mastery']:.0%} · "
                    f"Risk: {s['risk_score']:.2f}"
                )

    # ── INDIVIDUAL STUDENT TAB ────────────────────────────────
    with tab_student:
        st.subheader("Individual Student Analytics")
        students = get_all_students(course_id)
        names = [s["name"] for s in students] if students else []

        if names:
            selected = st.selectbox("Select student", names)
            student_id = next(
                s["id"] for s in students if s["name"] == selected)
            data = get_student_summary(student_id, course_id)

            if data:
                st.metric("Risk Score", f"{data['risk_score']:.2f}")
                st.metric("Days since last login",
                          data["days_since_login"])
                st.divider()
                st.write("**Topic Mastery Breakdown**")
                for t in data["topics"]:
                    col_a, col_b = st.columns([4, 4])
                    with col_a:
                        st.write(t["topic"])
                    with col_b:
                        st.progress(t["mastery"])

    # ── ADVISORY CHATBOT TAB ──────────────────────────────────
    with tab_chat:
        st.subheader("Advisory Chatbot")
        st.caption("Ask about any student's risks, weaknesses, or progress.")

        if "prof_chat" not in st.session_state:
            st.session_state.prof_chat = []

        for turn in st.session_state.prof_chat:
            with st.chat_message("user"):
                st.write(turn["q"])
            with st.chat_message("assistant"):
                st.write(turn["a"])

        question = st.chat_input(
            "e.g. What are the risks for student Ali?")
        if question:
            students = get_all_students(course_id)
            student_id = None
            for s in (students or []):
                if s["name"].lower() in question.lower():
                    student_id = s["id"]
                    break

            with st.spinner("Analysing..."):
                if student_id:
                    reply = advise_on_student(
                        student_id, course_id, question)
                else:
                    reply = ("I couldn't identify a specific student in "
                             "your question. Please include the student's "
                             "name.")

            with st.chat_message("user"):
                st.write(question)
            with st.chat_message("assistant"):
                st.write(reply)

            st.session_state.prof_chat.append(
                {"q": question, "a": reply})