"""Pydantic schemas for Memory API request/response."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

MemoryType = Literal["pdf", "image", "video", "text", "webpage"]
MemoryStatus = Literal["processing", "ready", "failed"]


class MemoryCreate(BaseModel):
    """Payload for creating a new memory (userId set from auth)."""

    type: MemoryType = Field(..., description="Content type")
    contentHash: str = Field(..., description="Unique hash of the content")
    title: Optional[str] = None
    summary: Optional[str] = None
    extractedText: Optional[str] = None
    sourceUrl: Optional[str] = None
    status: MemoryStatus = Field(default="processing", description="Processing status")


class MemoryUpdate(BaseModel):
    """Payload for updating memory metadata (partial)."""

    title: Optional[str] = None
    summary: Optional[str] = None
    extractedText: Optional[str] = None
    sourceUrl: Optional[str] = None
    status: Optional[MemoryStatus] = None


class MemoryResponse(BaseModel):
    """Memory as returned by the API."""

    id: str
    userId: str
    type: str
    title: Optional[str] = None
    summary: Optional[str] = None
    extractedText: Optional[str] = None
    sourceUrl: Optional[str] = None
    contentHash: str
    status: str
    createdAt: datetime
    updatedAt: datetime
    tags: Optional[list[str]] = None  # Populated on single-memory GET

    model_config = {"from_attributes": True}
