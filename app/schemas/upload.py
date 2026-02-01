"""Pydantic schemas for Upload API."""

from datetime import datetime

from pydantic import BaseModel


class UploadResponse(BaseModel):
    """Upload record as returned by the API."""

    id: str
    memoryId: str
    fileUrl: str
    fileType: str
    mimeType: str | None
    fileSize: int
    createdAt: datetime

    model_config = {"from_attributes": True}
