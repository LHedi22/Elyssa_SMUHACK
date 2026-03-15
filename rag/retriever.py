# rag/retriever.py
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct,
    Filter, FieldCondition, MatchValue
)
from sentence_transformers import SentenceTransformer
from sentence_transformers.cross_encoder import CrossEncoder
from rank_bm25 import BM25Okapi
import uuid
import config

qdrant   = QdrantClient(host=config.QDRANT_HOST, port=config.QDRANT_PORT)
embedder = SentenceTransformer(config.EMBED_MODEL)
reranker = CrossEncoder("cross-encoder/nli-MiniLM2-L6-H768")


def create_collection(course_id: str):
    """Create a Qdrant collection for a course if it doesn't exist."""
    existing = [c.name for c in qdrant.get_collections().collections]
    if course_id not in existing:
        qdrant.create_collection(
            collection_name=course_id,
            vectors_config=VectorParams(size=384, distance=Distance.COSINE)
        )


def upsert_chunks(course_id: str, chunks: list[dict]):
    """Embed and store chunks in Qdrant with metadata."""
    create_collection(course_id)
    points = []
    for chunk in chunks:
        vector = embedder.encode(chunk["text"]).tolist()
        points.append(PointStruct(
            id=str(uuid.uuid4()),
            vector=vector,
            payload={
                "text":     chunk["text"],
                "chapter":  chunk.get("chapter", ""),
                "topic":    chunk.get("topic", ""),
                "filename": chunk.get("filename", ""),
                "page":     chunk.get("page", 0),
            }
        ))
    qdrant.upsert(collection_name=course_id, points=points)


def hybrid_search(course_id: str, query: str,
                  chapter_filter: str = None) -> list[dict]:
    """
    Hybrid retrieval: dense (Qdrant) + sparse (BM25) + reranking.
    Returns top-5 most relevant chunks.
    """
    # Check collection exists
    existing = [c.name for c in qdrant.get_collections().collections]
    if course_id not in existing:
        return []

    query_vec = embedder.encode(query).tolist()

    # Build optional chapter filter
    qdrant_filter = None
    if chapter_filter:
        qdrant_filter = Filter(must=[
            FieldCondition(
                key="chapter",
                match=MatchValue(value=chapter_filter)
            )
        ])

    # ── Dense retrieval (new API) ─────────────────────────────
    dense_result = qdrant.query_points(
        collection_name=course_id,
        query=query_vec,
        query_filter=qdrant_filter,
        limit=config.TOP_K_DENSE
    )
    dense_docs = [
        {"text": p.payload["text"], "meta": p.payload}
        for p in dense_result.points
    ]

    # ── BM25 sparse retrieval ─────────────────────────────────
    scroll_result = qdrant.scroll(
        collection_name=course_id,
        scroll_filter=qdrant_filter,
        limit=2000,
        with_payload=True
    )
    all_points = scroll_result[0]

    if not all_points:
        return dense_docs[:config.TOP_K_RERANK]

    corpus_texts = [p.payload["text"] for p in all_points]
    corpus_meta  = [p.payload for p in all_points]

    tokenized   = [t.lower().split() for t in corpus_texts]
    bm25        = BM25Okapi(tokenized)
    bm25_scores = bm25.get_scores(query.lower().split())

    top_bm25_idx = sorted(
        range(len(bm25_scores)),
        key=lambda i: bm25_scores[i],
        reverse=True
    )[:config.TOP_K_SPARSE]

    sparse_docs = [
        {"text": corpus_texts[i], "meta": corpus_meta[i]}
        for i in top_bm25_idx
    ]

    # ── Reciprocal Rank Fusion ────────────────────────────────
    fused = _rrf_merge(dense_docs, sparse_docs)

    # ── Cross-encoder reranking ───────────────────────────────
    # ── Cross-encoder reranking ───────────────────────────────
    if not fused:
        return []

    pairs         = [[query, doc["text"]] for doc in fused]
    raw_scores    = reranker.predict(pairs, apply_softmax=True)

    # NLI model returns [contradiction, neutral, entailment] per pair
    # We use the entailment score (index 2) as the relevance signal
    import numpy as np
    scores_array = np.array(raw_scores)

    if scores_array.ndim == 2:
        # Shape (N, 3) — extract entailment column
        rerank_scores = scores_array[:, 2].tolist()
    else:
        # Shape (N,) — already scalar scores, use directly
        rerank_scores = scores_array.tolist()

    reranked = sorted(
        zip(fused, rerank_scores),
        key=lambda x: x[1],
        reverse=True
    )
    MIN_RELEVANCE = 0.10
    filtered = [
        doc for doc, score in reranked[:config.TOP_K_RERANK]
        if float(score) >= MIN_RELEVANCE
    ]
    return filtered

def _rrf_merge(list_a: list, list_b: list, k: int = 60) -> list:
    """Reciprocal Rank Fusion of two ranked lists."""
    scores   = {}
    all_docs = {}

    for rank, doc in enumerate(list_a):
        key = doc["text"][:80]
        scores[key]   = scores.get(key, 0) + 1 / (k + rank + 1)
        all_docs[key] = doc

    for rank, doc in enumerate(list_b):
        key = doc["text"][:80]
        scores[key]   = scores.get(key, 0) + 1 / (k + rank + 1)
        all_docs[key] = doc

    sorted_keys = sorted(scores, key=scores.get, reverse=True)
    return [all_docs[k] for k in sorted_keys[:20]]


def get_chapters(course_id: str) -> list[str]:
    """
    Return all unique chapter names stored in the collection.
    Used to dynamically populate the chapter dropdowns.
    """
    existing = [c.name for c in qdrant.get_collections().collections]
    if course_id not in existing:
        return []

    all_points, _ = qdrant.scroll(
        collection_name=course_id,
        limit=2000,
        with_payload=True,
        with_vectors=False
    )

    chapters = sorted(set(
        p.payload.get("chapter", "")
        for p in all_points
        if p.payload.get("chapter", "")
    ))
    return chapters