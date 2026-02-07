"""YouTube video transcript extraction and optional Gemini processing."""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# Match youtube.com/watch?v=ID, youtu.be/ID, youtube.com/embed/ID, youtube.com/v/ID
YOUTUBE_VIDEO_ID_PATTERN = re.compile(
    r"(?:youtube\.com/(?:watch\?v=|embed/|v/)|youtu\.be/)([a-zA-Z0-9_-]{11})"
)


def is_youtube_url(url: str | None) -> bool:
    """Return True if url looks like a YouTube video URL."""
    if not url or not isinstance(url, str):
        return False
    url = url.strip()
    return bool(YOUTUBE_VIDEO_ID_PATTERN.search(url))


def extract_video_id(url: str) -> Optional[str]:
    """Extract YouTube video ID from URL. Returns None if not a valid YouTube URL."""
    if not url or not isinstance(url, str):
        return None
    m = YOUTUBE_VIDEO_ID_PATTERN.search(url.strip())
    return m.group(1) if m else None


def extract_youtube_transcript(url: str) -> tuple[str, Optional[float]]:
    """
    Fetch YouTube transcript for the given video URL.
    Returns (full transcript text, confidence or None).
    Uses youtube-transcript-api; no API key required.
    """
    video_id = extract_video_id(url)
    if not video_id:
        return "", None
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        ytt_api = YouTubeTranscriptApi()
        fetched = ytt_api.fetch(video_id)
        if not fetched:
            return "", None
        # FetchedTranscript is iterable; each item has .text
        parts = [snippet.text for snippet in fetched]
        text = " ".join(parts).strip()
        if text:
            return text[:500_000], None
    except Exception as e:
        logger.warning("YouTube transcript fetch failed for %s: %s", url[:50], e)
    return "", None


def extract_youtube_content(url: str) -> tuple[str, Optional[float]]:
    """
    Get YouTube video content: transcript only.
    Gemini summary/tags are applied later in the pipeline.
    """
    return extract_youtube_transcript(url)
