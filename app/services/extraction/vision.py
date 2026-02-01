"""Image understanding via Google Gemini vision. Describe what the image shows."""

import io
import logging
from pathlib import Path
from typing import Optional

from app.services.extraction.gemini_client import GEMINI_MODEL, get_client

logger = logging.getLogger(__name__)

# MIME types for inline image bytes (Gemini accepts these)
MIME_BY_EXT: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


def _mime_for_image(data: bytes, filename: str = "") -> str:
    """Guess MIME type from bytes or filename."""
    ext = Path(filename).suffix.lower() if filename else ""
    if ext and ext in MIME_BY_EXT:
        return MIME_BY_EXT[ext]
    # Fallback: detect from bytes (JPEG starts with ff d8, PNG with 89 50 4e)
    if data[:2] == b"\xff\xd8":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


def describe_image(data: bytes, filename: str = "image") -> tuple[str, Optional[float]]:
    """
    Send image to Gemini and ask what it shows. Returns (description, confidence).
    Use this for images with little/no text (photos, screenshots, diagrams).
    """
    client = get_client()
    if not client:
        return "", None
    mime = _mime_for_image(data, filename)
    prompt = (
        "Describe this image in detail. Include: "
        "what it shows (objects, people, scenery, context), "
        "any visible text, and the overall meaning or purpose. "
        "Be concise but thorough (2-5 sentences)."
    )
    try:
        from google.genai import types
        part = types.Part.from_bytes(data=data, mime_type=mime)
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[part, prompt],
        )
        if response and getattr(response, "text", None):
            return (response.text or "").strip(), None
    except Exception as e:
        logger.warning("Gemini vision describe_image failed: %s", e)
    return "", None
