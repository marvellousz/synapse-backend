"""Lightweight web search and page extraction for chat context."""

import logging
from dataclasses import dataclass
from typing import Optional
from urllib.parse import parse_qs, urljoin, urlparse

import httpx

from app.services.extraction.webpage import extract_webpage_content

logger = logging.getLogger(__name__)

DDG_SEARCH_URL = "https://html.duckduckgo.com/html/"
WEB_CONTEXT_MAX_CHARS = 6000


@dataclass
class WebSearchResult:
    title: str
    url: str
    snippet: str


def _normalize_ddg_url(href: str | None) -> str | None:
    if not href:
        return None

    href = href.strip()
    if not href:
        return None

    parsed = urlparse(href)
    if parsed.scheme in {"http", "https"}:
        return href

    if href.startswith("//"):
        return f"https:{href}"

    query = parse_qs(parsed.query)
    uddg = query.get("uddg", [None])[0]
    if uddg:
        return uddg

    return urljoin("https://duckduckgo.com", href)


async def search_web(query: str, *, limit: int = 3) -> list[WebSearchResult]:
    if not query.strip():
        return []

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True, headers=headers) as client:
            response = await client.get(DDG_SEARCH_URL, params={"q": query})
            response.raise_for_status()
    except Exception as exc:
        logger.warning("Web search failed for %s: %s", query[:80], exc)
        return []

    try:
        from bs4 import BeautifulSoup
    except ImportError:
        logger.warning("BeautifulSoup is not installed; web search results cannot be parsed")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    results: list[WebSearchResult] = []

    for item in soup.select("div.result"):
        anchor = item.select_one("a.result__a")
        if not anchor:
            continue

        title = anchor.get_text(" ", strip=True)
        url = _normalize_ddg_url(anchor.get("href"))
        if not url:
            continue

        snippet_node = item.select_one("a.result__snippet, div.result__snippet")
        snippet = snippet_node.get_text(" ", strip=True) if snippet_node else ""

        results.append(WebSearchResult(title=title, url=url, snippet=snippet))
        if len(results) >= limit:
            break

    return results


def _format_result_excerpt(title: str, url: str, snippet: str, page_text: str) -> str:
    excerpt = page_text.strip().replace("\n", " ")
    if len(excerpt) > 700:
        excerpt = f"{excerpt[:700].rstrip()}..."

    lines = [f"## {title}", f"URL: {url}"]
    if snippet:
        lines.append(f"Snippet: {snippet}")
    if excerpt:
        lines.append(f"Page excerpt: {excerpt}")
    return "\n".join(lines)


async def build_web_context(query: str, *, limit: int = 3) -> str:
    results = await search_web(query, limit=limit)
    if not results:
        return ""

    parts: list[str] = []
    for result in results:
        page_text, _ = extract_webpage_content(result.url)
        if not page_text:
            page_text = result.snippet
        parts.append(_format_result_excerpt(result.title, result.url, result.snippet, page_text))

    return "\n\n".join(parts).strip()[:WEB_CONTEXT_MAX_CHARS]