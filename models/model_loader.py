# models/model_loader.py
from transformers import pipeline
from sentence_transformers import SentenceTransformer, CrossEncoder
import requests
import config

def load_intent_classifier():
    return pipeline(
        "zero-shot-classification",
        model="typeform/distilbert-base-uncased-mnli",
        device=-1
    )

def load_nli_cross_encoder():
    return CrossEncoder("cross-encoder/nli-MiniLM2-L6-H768")

def load_ner():
    return pipeline(
        "ner",
        model="dslim/bert-base-NER",
        aggregation_strategy="simple",
        device=-1
    )

def call_llm(model: str, system_prompt: str, user_prompt: str,
             temperature: float = 0.3) -> str:
    response = requests.post(
        f"{config.OLLAMA_BASE_URL}/api/generate",
        json={
            "model": model,
            "prompt": f"<|system|>{system_prompt}<|end|>"
                      f"<|user|>{user_prompt}<|end|><|assistant|>",
            "stream": False,
            "options": {"temperature": temperature, "num_ctx": 4096}
        },
        timeout=120
    )
    return response.json()["response"].strip()

# Add to models/model_loader.py

_embedder = None

def get_embedder():
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer
        import config
        _embedder = SentenceTransformer(config.EMBED_MODEL)
    return _embedder