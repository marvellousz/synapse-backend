"""Webpage content extraction: fetch HTML and extract main text."""

import logging
import re
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


def _is_http_url(url: str | None) -> bool:
    if not url or not isinstance(url, str):
        return False
    url = url.strip()
    return url.startswith("http://") or url.startswith("https://")


def _extract_text_from_html(html: str) -> str:
    """Extract main text from HTML, stripping scripts, nav, etc."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        # Fallback: strip tags with regex
        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:500_000]
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)
    lines = (line.strip() for line in text.splitlines() if line.strip())
    text = "\n\n".join(lines)
    return text[:500_000] if text else ""


def extract_webpage_content(url: str) -> tuple[str, Optional[float]]:
    """
    Fetch webpage and extract main text. Uses httpx + BeautifulSoup.
    Returns (extracted_text, confidence). Confidence is None.
    """
    if not _is_http_url(url):
        return "", None
    try:
        with httpx.Client(follow_redirects=True, timeout=30.0) as client:
            resp = client.get(url)
            resp.raise_for_status()
            html = resp.text
        text = _extract_text_from_html(html)
        if text and len(text.strip()) > 50:
            return text.strip(), None
    except Exception as e:
        logger.warning("Webpage fetch/extract failed for %s: %s", url[:50], e)
    return "", None
