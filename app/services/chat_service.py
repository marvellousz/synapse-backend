"""
RAG chat: answer user questions using context from their memories.

1. Retrieve relevant chunks via semantic search over user's memories.
2. Build a prompt with context + optional conversation history + new message.
3. Generate reply with Gemini.
"""

import logging
import re
from datetime import date, datetime, timezone
from typing import Optional

from prisma.models import Memory as PrismaMemory

from app.config import GEMINI_API_KEY
from app.services.extraction.gemini_client import GEMINI_MODEL, get_client
from app.services.internet_search import build_web_context
from app.services.search_service import search_by_content

logger = logging.getLogger(__name__)

# Max context chars to include in prompt (avoid token limits)
CHAT_CONTEXT_MAX_CHARS = 8000

# Max conversation history turns to include
CHAT_HISTORY_MAX_TURNS = 10

_BROAD_MEMORY_QUERY_PATTERN = re.compile(
    r"\b(all my memories|full context|context of my memories|my memories|everything i know|what memories|latest memories|recent memories|memories i added|added today|today)\b",
    re.IGNORECASE,
)


def _normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _is_broad_memory_query(message: str) -> bool:
    return bool(_BROAD_MEMORY_QUERY_PATTERN.search(message))


def _is_today_query(message: str) -> bool:
    lowered = message.lower()
    return "today" in lowered or "added today" in lowered


def _build_memory_overview_context(memories: list[PrismaMemory], *, today_only: bool = False) -> str:
    parts: list[str] = []
    today_utc = datetime.now(timezone.utc).date()

    for memory in memories:
        created_at = _normalize_datetime(memory.createdAt)
        if today_only and created_at.date() != today_utc:
            continue

        tags = []
        if hasattr(memory, "tags") and memory.tags:
            tags = [mt.tag.name for mt in memory.tags if getattr(mt, "tag", None) and getattr(mt.tag, "name", None)]

        summary = (memory.summary or memory.extractedText or "").strip()
        source_url = (memory.sourceUrl or "").strip()
        category = memory.category or "Miscellaneous"

        section = [
            f"## {memory.title or 'Untitled'}",
            f"Created: {created_at.isoformat()}",
            f"Type: {memory.type}",
            f"Category: {category}",
        ]
        if summary:
            section.append(f"Summary: {summary}")
        if source_url:
            section.append(f"Source: {source_url}")
        if tags:
            section.append(f"Tags: {', '.join(tags)}")

        parts.append("\n".join(section))

    return "\n\n".join(parts).strip()[:CHAT_CONTEXT_MAX_CHARS]


def _build_context_from_results(results: list[dict]) -> str:
    """Format search results into a single context string for the prompt."""
    parts = []
    for r in results:
        title = r.get("title") or "Untitled"
        summary = (r.get("summary") or "").strip()
        matches = r.get("matches") or []
        chunks = [m.get("chunk", "").strip() for m in matches if m.get("chunk")]
        if summary:
            parts.append(f"## {title}\nSummary: {summary}")
        if chunks:
            parts.append(f"## {title}\nRelevant excerpts:\n" + "\n".join(f"- {c}" for c in chunks if c))
    return "\n\n".join(parts).strip()[:CHAT_CONTEXT_MAX_CHARS]


def _build_prompt(
    user_message: str,
    context: str,
    history: list[dict],
    *,
    internet_enabled: bool = False,
) -> str:
    """Build full prompt: system + context + history + new message."""
    system = (
        "You are a helpful assistant. The user has a personal knowledge base (memories) of notes, "
        "documents, and saved content. Answer their questions using the provided context. If internet "
        "context is enabled, use it as supplemental context for current or factual questions. If the answer "
        "cannot be found in the context, say so clearly. Keep answers concise and grounded in the provided "
        "context."
    )
    parts = [f"{system}\n\n---\n\nContext from the user's memories and web sources:\n\n{context}" if context else system]

    if history:
        # Include last N turns
        for turn in history[-CHAT_HISTORY_MAX_TURNS * 2 :]:
            role = turn.get("role", "")
            content = (turn.get("content") or "").strip()
            if not content:
                continue
            if role == "user":
                parts.append(f"\nUser: {content}")
            elif role == "assistant":
                parts.append(f"\nAssistant: {content}")

    parts.append(f"\nUser: {user_message.strip()}\nAssistant:")
    return "\n".join(parts)


async def generate_chat_reply(
    user_id: str,
    message: str,
    history: Optional[list[dict]] = None,
    use_internet: bool = False,
) -> str:
    """
    Generate a chat reply using RAG over the user's memories.

    Args:
        user_id: Current user ID (for memory scope).
        message: Latest user message.
        history: Optional list of { role: "user"|"assistant", content: str }.

    Returns:
        Assistant reply text, or error message if generation fails.
    """
    if not message or not message.strip():
        return "Please ask a question."

    history = history or []

    # 1. Retrieve relevant context from memories
    try:
        if _is_broad_memory_query(message):
            memories = await PrismaMemory.prisma().find_many(
                where={"userId": user_id},
                include={"tags": {"include": {"tag": True}}},
                order={"createdAt": "desc"},
            )
            if _is_today_query(message):
                context = _build_memory_overview_context(memories, today_only=True)
                if not context:
                    context = "No memories were added today."
            else:
                context = _build_memory_overview_context(memories[:25])
                if not context:
                    context = "No memories found in your knowledge base."
        else:
            results = await search_by_content(
                query=message,
                user_id=user_id,
                limit=8,
                content_type_filter=None,
            )
            context = _build_context_from_results(results) if results else ""

        if use_internet:
            web_context = await build_web_context(message, limit=3)
            if web_context:
                context = f"{context}\n\n---\n\nContext from the web:\n\n{web_context}" if context else web_context
    except Exception as e:
        logger.warning("Chat search failed: %s", e)
        context = ""

    if not context:
        context = "(No relevant memories found for this question.)"

    # 2. Build prompt
    prompt = _build_prompt(message, context, history, internet_enabled=use_internet)

    # 3. Generate with Gemini
    client = get_client()
    if not client or not GEMINI_API_KEY:
        return "Chat is not available (missing API key)."

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )
        if response and getattr(response, "text", None):
            return response.text.strip()
    except Exception as e:
        logger.warning("Chat Gemini failed: %s", e)
        return "Sorry, I couldn't generate a reply. Please try again."
    return "Sorry, I couldn't generate a reply."