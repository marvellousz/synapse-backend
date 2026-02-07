"""Chat API: RAG chat with context from user's memories."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from prisma.models import User

from app.core.auth import get_current_user
from app.services.chat_service import generate_chat_reply

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatMessage(BaseModel):
    """Single message in conversation history."""

    role: str = Field(..., description="'user' or 'assistant'")
    content: str = Field(..., description="Message text")


class ChatRequest(BaseModel):
    """Request body for chat endpoint."""

    message: str = Field(..., min_length=1, description="Latest user message")
    history: list[ChatMessage] = Field(default_factory=list, description="Previous messages (optional)")


class ChatResponse(BaseModel):
    """Response from chat endpoint."""

    reply: str = Field(..., description="Assistant reply")


@router.post("", response_model=ChatResponse)
async def chat_endpoint(
    body: ChatRequest,
    current_user: User = Depends(get_current_user),
) -> ChatResponse:
    """
    Send a message and get a reply grounded in the user's memories.

    Uses semantic search over the user's memories to retrieve relevant context,
    then generates a reply with Gemini. Optional conversation history improves
    follow-up answers.
    """
    if not body.message or not body.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    history = [{"role": m.role, "content": m.content} for m in body.history]
    reply = await generate_chat_reply(
        user_id=current_user.id,
        message=body.message.strip(),
        history=history,
    )
    return ChatResponse(reply=reply)
