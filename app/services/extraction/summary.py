"""Auto-generated summaries via Google Gemini."""

import logging
from typing import Optional

from app.config import EXTRACTION_SUMMARY_MAX_CHARS
from app.services.extraction.gemini_client import GEMINI_MODEL, get_client

logger = logging.getLogger(__name__)


def generate_summary(extracted_text: str, title: Optional[str] = None) -> str:
    """
    Generate a short summary of the content using Google Gemini.
    If no API key or empty text, returns empty string.
    """
    if not extracted_text.strip():
        return ""
    client = get_client()
    if not client:
        return ""
    text = extracted_text[:EXTRACTION_SUMMARY_MAX_CHARS]
    if len(extracted_text) > EXTRACTION_SUMMARY_MAX_CHARS:
        text += "\n\n[Truncated...]"
    prompt = "Summarize the following content in 2-4 concise sentences. Preserve key facts and ideas.\n\n"
    if title:
        prompt += f"Title: {title}\n\n"
    prompt += "Content:\n" + text
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )
        if response and getattr(response, "text", None):
            return response.text.strip()
    except Exception as e:
        logger.warning("Gemini summary failed: %s", e)
    return ""

