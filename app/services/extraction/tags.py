"""Content classification and tagging via Google Gemini."""

import logging
from typing import Optional

from app.config import EXTRACTION_SUMMARY_MAX_CHARS
from app.services.extraction.gemini_client import GEMINI_MODEL, get_client

logger = logging.getLogger(__name__)


def generate_tags(extracted_text: str, title: Optional[str] = None) -> list[str]:
    """
    Generate 3-8 topic tags from the content (lowercase, no spaces in a tag).
    Returns list of tag strings.
    """
    if not extracted_text.strip():
        return []
    client = get_client()
    if not client:
        return []
    text = extracted_text[:EXTRACTION_SUMMARY_MAX_CHARS]
    if len(extracted_text) > EXTRACTION_SUMMARY_MAX_CHARS:
        text += "\n\n[Truncated...]"
    prompt = "From the following content, suggest 3-8 short topic tags (lowercase, comma-separated, no spaces inside a tag, e.g. machine-learning, productivity). Only output the tags, nothing else.\n\n"
    if title:
        prompt += f"Title: {title}\n\n"
    prompt += "Content:\n" + text
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )
        if response and getattr(response, "text", None):
            raw = response.text.strip()
            tags = [t.strip().lower().replace(" ", "-") for t in raw.split(",") if t.strip()]
            return tags[:8]
    except Exception as e:
        logger.warning("Gemini tags failed: %s", e)
    return []
