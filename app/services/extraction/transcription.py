"""Audio/video transcription via Google Gemini."""

import tempfile
from pathlib import Path
from typing import Optional

from app.services.extraction.gemini_client import GEMINI_MODEL, get_client


def transcribe_audio(data: bytes, filename: str = "audio") -> tuple[str, Optional[float]]:
    """
    Transcribe audio/video bytes using Google Gemini.
    Returns (text, confidence). Gemini doesn't return confidence; we use None.
    """
    client = get_client()
    if not client:
        return "", None
    suffix = Path(filename).suffix or ".mp4"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(data)
        path = f.name
    try:
        uploaded = client.files.upload(file=path)
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=["Transcribe this audio or video. Output only the raw transcript text, nothing else.", uploaded],
        )
        if response and response.text:
            return (response.text or "").strip(), None
        return "", None
    except Exception:
        return "", None
    finally:
        Path(path).unlink(missing_ok=True)
