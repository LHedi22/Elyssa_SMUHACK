from dotenv import load_dotenv
import os

load_dotenv()

QDRANT_HOST          = os.getenv("QDRANT_HOST",          "localhost")
QDRANT_PORT          = int(os.getenv("QDRANT_PORT",      "6333"))
OLLAMA_BASE_URL      = os.getenv("OLLAMA_BASE_URL",      "http://localhost:11434")
TUTOR_MODEL          = os.getenv("TUTOR_MODEL",          "phi3")
ASSESSMENT_MODEL     = os.getenv("ASSESSMENT_MODEL",     "qwen2.5:3b")
ADVISORY_MODEL       = os.getenv("ADVISORY_MODEL",       "phi3")
MONGO_URI            = os.getenv("MONGO_URI",            "mongodb://localhost:27017")
MONGO_DB_NAME        = os.getenv("MONGO_DB_NAME",        "studymate")
EMBED_MODEL          = os.getenv("EMBED_MODEL",          "all-MiniLM-L6-v2")
CHUNK_SIZE           = int(os.getenv("CHUNK_SIZE",       "512"))
CHUNK_OVERLAP        = int(os.getenv("CHUNK_OVERLAP",    "64"))
TOP_K_DENSE          = int(os.getenv("TOP_K_DENSE",      "20"))
TOP_K_SPARSE         = int(os.getenv("TOP_K_SPARSE",     "20"))
TOP_K_RERANK         = int(os.getenv("TOP_K_RERANK",     "5"))
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.60"))
MASTERY_THRESHOLD    = float(os.getenv("MASTERY_THRESHOLD",    "0.80"))