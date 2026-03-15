# debug_upload.py
import sys, os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_pipeline(file_path: str, course_id: str = "CS301",
                  chapter: str = "Chapter 1"):

    print(f"\n{'='*60}")
    print(f"Testing upload pipeline")
    print(f"File    : {file_path}")
    print(f"Course  : {course_id}")
    print(f"Chapter : {chapter}")
    print(f"{'='*60}\n")

    # ── Step 1: Check file exists ─────────────────────────────
    print("[1] Checking file exists...")
    if not os.path.exists(file_path):
        print(f"    FAIL — file not found: {file_path}")
        return
    print(f"    OK — file size: {os.path.getsize(file_path)} bytes")

    # ── Step 2: Parse with Tika ───────────────────────────────
    print("\n[2] Parsing with Tika...")
    try:
        from tika import parser as tika_parser
        parsed  = tika_parser.from_file(file_path)
        content = parsed.get("content") or ""
        content = content.strip()
        if not content:
            print("    FAIL — Tika returned empty content")
            print("    Trying PyMuPDF fallback...")
            try:
                import fitz
                doc   = fitz.open(file_path)
                content = ""
                for page in doc:
                    content += page.get_text()
                doc.close()
                print(f"    PyMuPDF OK — extracted {len(content)} chars")
            except Exception as e2:
                print(f"    PyMuPDF also failed: {e2}")
                return
        else:
            print(f"    OK — extracted {len(content)} characters")
            print(f"    First 200 chars: {content[:200]!r}")
    except Exception as e:
        print(f"    FAIL — Tika error: {e}")
        return

    # ── Step 3: Chunk ─────────────────────────────────────────
    print("\n[3] Chunking text...")
    words  = content.split()
    print(f"    Total words: {len(words)}")

    chunks_text = []
    chunk_size, overlap = 512, 64
    start = 0
    while start < len(words):
        end   = start + chunk_size
        chunk = " ".join(words[start:end])
        if chunk.strip():
            chunks_text.append(chunk)
        start += chunk_size - overlap

    print(f"    OK — created {len(chunks_text)} chunks")
    if chunks_text:
        print(f"    First chunk preview: {chunks_text[0][:100]}...")

    # ── Step 4: Load embedder ─────────────────────────────────
    print("\n[4] Loading embedding model...")
    try:
        from sentence_transformers import SentenceTransformer
        import config
        embedder = SentenceTransformer(config.EMBED_MODEL)
        test_vec = embedder.encode("test sentence")
        print(f"    OK — vector size: {len(test_vec)}")
    except Exception as e:
        print(f"    FAIL — embedder error: {e}")
        return

    # ── Step 5: Connect to Qdrant ─────────────────────────────
    print("\n[5] Connecting to Qdrant...")
    try:
        from qdrant_client import QdrantClient
        qdrant = QdrantClient(host=config.QDRANT_HOST,
                              port=config.QDRANT_PORT)
        qdrant.get_collections()
        print("    OK — Qdrant connected")
    except Exception as e:
        print(f"    FAIL — Qdrant error: {e}")
        print("    Is Docker running? Is Qdrant container started?")
        return

    # ── Step 6: Create collection ─────────────────────────────
    print(f"\n[6] Creating/verifying collection '{course_id}'...")
    try:
        from qdrant_client.models import Distance, VectorParams
        existing = [c.name for c in qdrant.get_collections().collections]
        if course_id not in existing:
            qdrant.create_collection(
                collection_name=course_id,
                vectors_config=VectorParams(size=384, distance=Distance.COSINE)
            )
            print(f"    OK — collection created")
        else:
            info = qdrant.get_collection(course_id)
            print(f"    OK — collection exists "
                  f"({info.points_count} points already)")
    except Exception as e:
        print(f"    FAIL — {e}")
        return

    # ── Step 7: Embed and insert ONE chunk as a test ──────────
    print("\n[7] Embedding and inserting first chunk as test...")
    try:
        import uuid
        from qdrant_client.models import PointStruct

        first_chunk = chunks_text[0]
        vector      = embedder.encode(first_chunk).tolist()

        qdrant.upsert(
            collection_name=course_id,
            points=[PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload={
                    "text":     first_chunk,
                    "chapter":  chapter,
                    "filename": os.path.basename(file_path),
                    "page":     0
                }
            )]
        )
        info = qdrant.get_collection(course_id)
        print(f"    OK — point inserted. Collection now has "
              f"{info.points_count} points")
    except Exception as e:
        print(f"    FAIL — insert error: {e}")
        return

    # ── Step 8: Insert ALL remaining chunks ───────────────────
    print(f"\n[8] Inserting remaining {len(chunks_text)-1} chunks...")
    try:
        from qdrant_client.models import PointStruct
        import uuid

        points = []
        for i, chunk in enumerate(chunks_text[1:], start=1):
            vector = embedder.encode(chunk).tolist()
            points.append(PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload={
                    "text":     chunk,
                    "chapter":  chapter,
                    "filename": os.path.basename(file_path),
                    "page":     i
                }
            ))
            if (i + 1) % 5 == 0:
                print(f"    Embedded {i+1}/{len(chunks_text)}...")

        if points:
            qdrant.upsert(collection_name=course_id, points=points)

        info = qdrant.get_collection(course_id)
        print(f"    OK — all done. Collection now has "
              f"{info.points_count} total points")
    except Exception as e:
        print(f"    FAIL — {e}")
        return

    # ── Step 9: Test search ───────────────────────────────────
    print("\n[9] Running test vector search...")
    try:
        query_vec = embedder.encode(
            chunks_text[0].split()[:10].__str__()
        ).tolist()
        results = qdrant.query_points(
            collection_name=course_id,
            query=query_vec,
            limit=3
        )
        print(f"    OK — search returned {len(results.points)} results")
        for r in results.points:
            print(f"    Score {round(r.score,4)} | "
                  f"{r.payload.get('filename')} "
                  f"p{r.payload.get('page')}")
    except Exception as e:
        print(f"    FAIL — search error: {e}")

    print(f"\n{'='*60}")
    print("Pipeline test complete.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python debug_upload.py <path_to_pdf>")
        print("Example: python debug_upload.py lecture1.pdf")
    else:
        test_pipeline(sys.argv[1])