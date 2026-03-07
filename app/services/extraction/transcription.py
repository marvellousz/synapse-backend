"""Audio/video transcription via Google Gemini."""

import tempfile
import logging
from pathlib import Path
from typing import Optional

from app.config import GEMINI_INLINE_VIDEO_MAX_BYTES
from app.services.extraction.gemini_client import GEMINI_MODEL, get_client

logger = logging.getLogger(__name__)

TRANSCRIPTION_PROMPT = "Transcribe this audio or video. Output only the raw transcript text, nothing else."


def transcribe_audio(data: bytes, filename: str = "audio") -> tuple[str, Optional[float]]:
    """
    Transcribe audio/video bytes using Google Gemini.
    Returns (text, confidence). Gemini doesn't return confidence; we use None.
    """
    client = get_client()
    if not client:
        return "", None
    # Use inline input for small media, otherwise use Files API upload for larger payloads.
    if len(data) <= GEMINI_INLINE_VIDEO_MAX_BYTES:
        try:
            from google.genai import types

            suffix = Path(filename).suffix.lower()
            mime_type = {
                ".mp4": "video/mp4",
                ".webm": "video/webm",
                ".mov": "video/quicktime",
                ".avi": "video/avi",
                ".mp3": "audio/mpeg",
                ".wav": "audio/wav",
                ".m4a": "audio/mp4",
            }.get(suffix, "video/mp4")

            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=types.Content(
                    parts=[
                        types.Part(
                            inline_data=types.Blob(data=data, mime_type=mime_type)
                        ),
                        types.Part(text=TRANSCRIPTION_PROMPT),
                    ]
                ),
            )
            if response and response.text:
                return (response.text or "").strip(), None
        except Exception as e:
            # Fall back to Files API path if inline call fails for any reason.
            logger.warning("Inline transcription failed; falling back to Files API: %s", e)

    suffix = Path(filename).suffix or ".mp4"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(data)
        path = f.name
    try:
        uploaded = client.files.upload(file=path)
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[TRANSCRIPTION_PROMPT, uploaded],
        )
        if response and response.text:
            return (response.text or "").strip(), None
        return "", None
    except Exception:
        return "", None
    finally:
        Path(path).unlink(missing_ok=True)
