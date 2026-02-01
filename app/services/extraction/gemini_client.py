"""
Shared Gemini client for extraction (summary, tags, transcription).
Uses GEMINI_API_KEY from the environment; client picks it up automatically
when set (e.g. in .env). Optional HttpOptions(api_version="v1") for stable API.
"""

import logging
from typing import Optional

from app.config import GEMINI_API_KEY

logger = logging.getLogger(__name__)
_client: Optional[object] = None

# Prefer gemini-2.5-flash per Google AI for Developers docs
GEMINI_MODEL = "gemini-2.5-flash"


def get_client() -> Optional[object]:
    """Return a configured Gemini client, or None if no API key."""
    global _client
    if _client is not None:
        return _client
    if not GEMINI_API_KEY:
        return None
    try:
        from google import genai
        try:
            from google.genai.types import HttpOptions
            _client = genai.Client(
                api_key=GEMINI_API_KEY,
                http_options=HttpOptions(api_version="v1"),
            )
        except (ImportError, AttributeError):
            _client = genai.Client(api_key=GEMINI_API_KEY)
    except ImportError as e:
        logger.warning("google-genai not installed: %s", e)
        _client = None
    return _client
