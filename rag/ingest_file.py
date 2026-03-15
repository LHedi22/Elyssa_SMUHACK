# rag/ingest_file.py
import os
from rag.ingestion_pipeline import parse_document, chunk_text
from rag.retriever import create_collection, upsert_chunks


def ingest_file(file_path: str,
                course_id: str,
                chapter: str,
                filename: str = None) -> dict:
    """
    Full pipeline: file → parse → chunk → embed → Qdrant.

    Returns a status dict with counts and any error message.
    """
    filename = filename or os.path.basename(file_path)

    # ── Step 1: Parse ─────────────────────────────────────────
    try:
        text = parse_document(file_path)
    except Exception as e:
        return {
            "success":  False,
            "error":    f"Parsing failed: {str(e)}",
            "chunks":   0,
            "filename": filename
        }

    if not text or len(text.strip()) < 20:
        return {
            "success":  False,
            "error":    "No readable text found in file.",
            "chunks":   0,
            "filename": filename
        }

    # ── Step 2: Chunk ─────────────────────────────────────────
    chunks_text = chunk_text(text)

    if not chunks_text:
        return {
            "success":  False,
            "error":    "Text was extracted but chunking produced no results.",
            "chunks":   0,
            "filename": filename
        }

    # ── Step 3: Build chunk dicts with metadata ───────────────
    chunks = [
        {
            "text":     c,
            "chapter":  chapter,
            "filename": filename,
            "page":     i,
        }
        for i, c in enumerate(chunks_text)
    ]

    # ── Step 4: Embed + insert into Qdrant ────────────────────
    try:
        create_collection(course_id)
        upsert_chunks(course_id, chunks)
    except Exception as e:
        return {
            "success":  False,
            "error":    f"Qdrant insert failed: {str(e)}",
            "chunks":   0,
            "filename": filename
        }

    return {
        "success":  True,
        "error":    None,
        "chunks":   len(chunks),
        "filename": filename,
        "chars":    len(text),
        "chapter":  chapter
    }