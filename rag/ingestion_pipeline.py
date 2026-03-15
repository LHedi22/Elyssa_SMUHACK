# rag/ingestion_pipeline.py
import os
import tempfile
from tika import parser as tika_parser
import pytesseract
from PIL import Image
import whisper

# Load Whisper once at module level
_whisper_model = None

def _get_whisper():
    global _whisper_model
    if _whisper_model is None:
        _whisper_model = whisper.load_model("base")
    return _whisper_model


def parse_document(file_path: str) -> str:
    """Route file to the correct parser based on extension."""
    ext = os.path.splitext(file_path)[1].lower()

    if ext in [".pdf", ".pptx", ".docx", ".txt", ".doc"]:
        return _parse_with_tika(file_path)
    elif ext in [".png", ".jpg", ".jpeg", ".tiff", ".bmp"]:
        return _parse_with_tesseract(file_path)
    elif ext in [".mp3", ".mp4", ".wav", ".m4a", ".ogg"]:
        return _parse_with_whisper(file_path)
    else:
        raise ValueError(f"Unsupported file type: {ext}")


def _parse_with_tika(file_path: str) -> str:
    parsed  = tika_parser.from_file(file_path)
    content = parsed.get("content") or ""
    return content.strip()


def _parse_with_tesseract(image_path: str) -> str:
    img  = Image.open(image_path)
    text = pytesseract.image_to_string(img, lang="eng")
    return text.strip()


def _parse_with_whisper(audio_path: str) -> str:
    model  = _get_whisper()
    result = model.transcribe(audio_path)
    return result["text"].strip()


def chunk_text(text: str,
               chunk_size: int = 512,
               overlap: int = 64) -> list[str]:
    """Split text into overlapping word-count chunks."""
    words  = text.split()
    chunks = []
    start  = 0
    while start < len(words):
        end   = start + chunk_size
        chunk = " ".join(words[start:end])
        if chunk.strip():
            chunks.append(chunk)
        start += chunk_size - overlap
    return chunks


# Add this to the bottom of rag/ingestion_pipeline.py

from transformers import pipeline as hf_pipeline

_ner_pipeline = None

def _get_ner():
    global _ner_pipeline
    if _ner_pipeline is None:
        _ner_pipeline = hf_pipeline(
            "ner",
            model="dslim/bert-base-NER",
            aggregation_strategy="simple",
            device=-1
        )
    return _ner_pipeline


def extract_concepts(text: str) -> list[str]:
    """
    Use BERT NER to extract technical concept entities from text.
    Used by the Topic Graph Builder during ingestion.
    """
    # NER has a 512 token limit — truncate to be safe
    truncated = text[:1000]
    try:
        ner    = _get_ner()
        entities = ner(truncated)
        concepts = [
            e["word"].strip()
            for e in entities
            if len(e["word"].strip()) > 2
        ]
        return list(set(concepts))
    except Exception:
        return []