# agents/supervision.py
from models.model_loader import load_nli_cross_encoder
from sentence_transformers import SentenceTransformer
import numpy as np, config

_nli = load_nli_cross_encoder()
_embedder = SentenceTransformer(config.EMBED_MODEL)

# agents/supervision.py
def check_grounding(answer: str, retrieved_chunks: list[dict]) -> dict:
    if not retrieved_chunks:
        return {"verdict": "fallback", "score": 0.0, "source": None}

    chunk_texts = [c["text"] for c in retrieved_chunks]
    pairs       = [(chunk, answer) for chunk in chunk_texts]
    raw_scores  = _nli.predict(pairs, apply_softmax=True)

    import numpy as np
    scores_array = np.array(raw_scores)

    if scores_array.ndim == 2:
        entailment_scores = scores_array[:, 2]
    else:
        entailment_scores = scores_array

    best_idx   = int(np.argmax(entailment_scores))
    best_score = float(entailment_scores[best_idx])
    best_chunk = retrieved_chunks[best_idx]

    if best_score >= 0.75:
        verdict = "pass"
    elif best_score >= 0.60:
        verdict = "uncertain"
    else:
        verdict = "fallback"

    return {
        "verdict": verdict,
        "score":   round(best_score, 3),
        "source": {
            "filename": best_chunk["meta"].get("filename", ""),
            "chapter":  best_chunk["meta"].get("chapter", ""),
            "page":     best_chunk["meta"].get("page", ""),
        }
    }

FALLBACK_MESSAGE = (
    "I cannot find a reliable answer to this question "
    "in your course materials. Please consult your professor or textbook."
)