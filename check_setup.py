# check_setup.py
import subprocess

def ok(label):
    print(f"  [OK]   {label}")

def fail(label, reason):
    print(f"  [FAIL] {label}: {reason}")

def check(label, fn):
    try:
        fn()
        ok(label)
    except Exception as e:
        fail(label, str(e)[:120])

print("\n=== StudyMate Setup Check ===\n")

# ── Services ──────────────────────────────────────────────────
import requests

check("Qdrant running on :6333",
    lambda: requests.get("http://localhost:6333/", timeout=3).raise_for_status())

check("Ollama running on :11434",
    lambda: requests.get("http://localhost:11434/api/tags", timeout=3).raise_for_status())

check("MongoDB running on :27017",
    lambda: __import__("pymongo").MongoClient(
        "mongodb://localhost:27017",
        serverSelectionTimeoutMS=3000
    ).admin.command("ping"))

# ── Ollama models ─────────────────────────────────────────────
try:
    resp = requests.get("http://localhost:11434/api/tags", timeout=3).json()
    names = [m["name"] for m in resp.get("models", [])]
    check("phi3 model pulled",
        lambda: (_ for _ in ()).throw(Exception("not found"))
        if not any("phi3" in n for n in names) else None)
    check("qwen2.5:3b model pulled",
        lambda: (_ for _ in ()).throw(Exception("not found"))
        if not any("qwen2.5" in n for n in names) else None)
except Exception as e:
    fail("Ollama model check", str(e))

# ── Python packages ───────────────────────────────────────────
packages = [
    "streamlit", "qdrant_client", "sentence_transformers",
    "rank_bm25", "transformers", "torch", "tika",
    "pytesseract", "whisper", "spacy", "networkx",
    "sklearn", "pymongo", "dotenv"
]
for pkg in packages:
    check(f"Python package: {pkg}", lambda p=pkg: __import__(p))

# ── HuggingFace models cached ─────────────────────────────────
from sentence_transformers import SentenceTransformer, CrossEncoder
from transformers import pipeline

check("Embedder cached (all-MiniLM-L6-v2)",
    lambda: SentenceTransformer("all-MiniLM-L6-v2"))

check("Intent classifier cached (distilbert-mnli)",
    lambda: pipeline("zero-shot-classification",
        model="typeform/distilbert-base-uncased-mnli", device=-1))

check("NLI cross-encoder cached (MiniLM2)",
    lambda: CrossEncoder("cross-encoder/nli-MiniLM2-L6-H768"))

check("NER model cached (bert-base-NER)",
    lambda: pipeline("ner", model="dslim/bert-base-NER",
        aggregation_strategy="simple", device=-1))

# ── System binaries ───────────────────────────────────────────
check("Java installed",
    lambda: subprocess.run(["java", "-version"],
        capture_output=True, check=True))

check("Tesseract installed",
    lambda: subprocess.run(["tesseract", "--version"],
        capture_output=True, check=True))

check("ffmpeg installed",
    lambda: subprocess.run(["ffmpeg", "-version"],
        capture_output=True, check=True))

print("\n=== Done. Fix any [FAIL] lines before running the app. ===\n")