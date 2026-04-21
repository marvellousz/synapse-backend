"""Auto-generated summaries via Google Gemini."""

import logging
from typing import Optional

from app.config import EXTRACTION_SUMMARY_MAX_CHARS
from app.services.extraction.gemini_client import GEMINI_MODEL, get_client

logger = logging.getLogger(__name__)


def generate_summary(extracted_text: str, title: Optional[str] = None) -> str:
    """
    Generate a short summary of the content using Google Gemini.
    If no API key or empty text, returns a truncated fallback.
    """
    if not extracted_text.strip():
        return ""
    
    # Fallback summary if Gemini fails or is missing
    fallback = extracted_text.strip()[:300]
    if len(extracted_text.strip()) > 300:
        fallback += "..."

    client = get_client()
    if not client:
        return fallback

    text = extracted_text[:EXTRACTION_SUMMARY_MAX_CHARS]
    if len(extracted_text) > EXTRACTION_SUMMARY_MAX_CHARS:
        text += "\n\n[Truncated...]"

    prompt = (
        "Generate a high-level EXECUTIVE SUMMARY of the following content. "
        "Keep it concise (2-4 sentences) but extremely informative. "
        "IMPORTANT: If the content is a recipe (even if it's a video transcript), you MUST explicitly list ALL ingredients and provide clear, numbered step-by-step instructions. "
        "Focus on the core message, key takeaways, and essential facts.\n\n"
    )
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
    
    return fallback

