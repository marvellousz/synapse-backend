"""Chats API: list, create, get, send message, delete (DB-backed chat history)."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from prisma.models import Chat as PrismaChat, ChatMessage as PrismaChatMessage, User

from app.core.auth import get_current_user
from app.services.chat_service import generate_chat_reply

router = APIRouter(prefix="/api/chats", tags=["chats"])


class ChatCreate(BaseModel):
    title: str | None = None


class ChatListItem(BaseModel):
    id: str
    title: str
    createdAt: str
    updatedAt: str


class MessageIn(BaseModel):
    role: str = Field(..., description="user or assistant")
    content: str


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    createdAt: str


class ChatOut(BaseModel):
    id: str
    title: str
    createdAt: str
    updatedAt: str
    messages: list[MessageOut]


class ChatUpdate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)


class SendMessageIn(BaseModel):
    message: str = Field(..., min_length=1)


class SendMessageOut(BaseModel):
    reply: str
    userMessageId: str
    assistantMessageId: str


@router.get("", response_model=list[ChatListItem])
async def list_chats(current_user: User = Depends(get_current_user)) -> list[ChatListItem]:
    """List current user's chats, newest first."""
    chats = await PrismaChat.prisma().find_many(
        where={"userId": current_user.id},
        order={"updatedAt": "desc"},
    )
    return [
        ChatListItem(
            id=c.id,
            title=c.title,
            createdAt=c.createdAt.isoformat(),
            updatedAt=c.updatedAt.isoformat(),
        )
        for c in chats
    ]


@router.post("", response_model=ChatListItem, status_code=201)
async def create_chat(
    body: ChatCreate | None = None,
    current_user: User = Depends(get_current_user),
) -> ChatListItem:
    """Create a new chat."""
    title = (body and body.title) or "New chat"
    chat = await PrismaChat.prisma().create(
        data={"userId": current_user.id, "title": title[:200]},
    )
    return ChatListItem(
        id=chat.id,
        title=chat.title,
        createdAt=chat.createdAt.isoformat(),
        updatedAt=chat.updatedAt.isoformat(),
    )


@router.get("/{chat_id}", response_model=ChatOut)
async def get_chat(
    chat_id: str,
    current_user: User = Depends(get_current_user),
) -> ChatOut:
    """Get a chat with all messages."""
    chat = await PrismaChat.prisma().find_first(
        where={"id": chat_id, "userId": current_user.id},
        include={"messages": True},
    )
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    return ChatOut(
        id=chat.id,
        title=chat.title,
        createdAt=chat.createdAt.isoformat(),
        updatedAt=chat.updatedAt.isoformat(),
        messages=[
            MessageOut(id=m.id, role=m.role, content=m.content, createdAt=m.createdAt.isoformat())
            for m in sorted(chat.messages, key=lambda x: x.createdAt)
        ],
    )


@router.patch("/{chat_id}", response_model=ChatListItem)
async def update_chat(
    chat_id: str,
    body: ChatUpdate,
    current_user: User = Depends(get_current_user),
) -> ChatListItem:
    """Update a chat (e.g. title)."""
    chat = await PrismaChat.prisma().find_first(
        where={"id": chat_id, "userId": current_user.id},
    )
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    updated = await PrismaChat.prisma().update(
        where={"id": chat_id},
        data={"title": body.title.strip()[:200]},
    )
    return ChatListItem(
        id=updated.id,
        title=updated.title,
        createdAt=updated.createdAt.isoformat(),
        updatedAt=updated.updatedAt.isoformat(),
    )


@router.post("/{chat_id}/messages", response_model=SendMessageOut)
async def send_message(
    chat_id: str,
    body: SendMessageIn,
    current_user: User = Depends(get_current_user),
) -> SendMessageOut:
    """Send a message; store user + assistant reply and return reply."""
    chat = await PrismaChat.prisma().find_first(
        where={"id": chat_id, "userId": current_user.id},
        include={"messages": True},
    )
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    history = [{"role": m.role, "content": m.content} for m in sorted(chat.messages, key=lambda x: x.createdAt)]
    reply = await generate_chat_reply(
        user_id=current_user.id,
        message=body.message.strip(),
        history=history,
    )

    user_msg = await PrismaChatMessage.prisma().create(
        data={"chatId": chat_id, "role": "user", "content": body.message.strip()},
    )
    assistant_msg = await PrismaChatMessage.prisma().create(
        data={"chatId": chat_id, "role": "assistant", "content": reply},
    )

    # Set title from first user message if still default
    if chat.title == "New chat" and body.message.strip():
        new_title = body.message.strip()[:80]
        if len(body.message.strip()) > 80:
            new_title += "..."
        await PrismaChat.prisma().update(
            where={"id": chat_id},
            data={"title": new_title, "updatedAt": assistant_msg.createdAt},
        )

    return SendMessageOut(
        reply=reply,
        userMessageId=user_msg.id,
        assistantMessageId=assistant_msg.id,
    )


@router.delete("/{chat_id}", status_code=204)
async def delete_chat(
    chat_id: str,
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete a chat and its messages."""
    chat = await PrismaChat.prisma().find_first(
        where={"id": chat_id, "userId": current_user.id},
    )
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    await PrismaChat.prisma().delete(where={"id": chat_id})
