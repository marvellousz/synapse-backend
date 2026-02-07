"""
RAG chat: answer user questions using context from their memories.

1. Retrieve relevant chunks via semantic search over user's memories.
2. Build a prompt with context + optional conversation history + new message.
3. Generate reply with Gemini.
"""

import logging
from typing import Optional

from app.config import GEMINI_API_KEY
from app.services.extraction.gemini_client import GEMINI_MODEL, get_client
from app.services.search_service import search_by_content

logger = logging.getLogger(__name__)

# Max context chars to include in prompt (avoid token limits)
CHAT_CONTEXT_MAX_CHARS = 8000

# Max conversation history turns to include
CHAT_HISTORY_MAX_TURNS = 10


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
) -> str:
    """Build full prompt: system + context + history + new message."""
    system = (
        "You are a helpful assistant. The user has a personal knowledge base (memories) of notes, "
        "documents, and saved content. Answer their questions using ONLY the following context from "
        "their memories. If the answer cannot be found in the context, say so clearly. Keep answers "
        "concise and grounded in the provided context."
    )
    parts = [f"{system}\n\n---\n\nContext from the user's memories:\n\n{context}" if context else system]

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
        results = await search_by_content(
            query=message,
            user_id=user_id,
            limit=8,
            content_type_filter=None,
        )
    except Exception as e:
        logger.warning("Chat search failed: %s", e)
        results = []

    context = _build_context_from_results(results) if results else ""
    if not context:
        context = "(No relevant memories found for this question.)"

    # 2. Build prompt
    prompt = _build_prompt(message, context, history)

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