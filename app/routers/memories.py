"""Memory CRUD API."""

from typing import Annotated, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from prisma.models import Embedding, Extraction, Memory as PrismaMemory, MemoryTag, SpaceMemory, Upload as PrismaUpload, User

from app.core.auth import get_current_user
from app.storage import storage
from app.schemas.memory import MemoryCreate, MemoryResponse, MemoryUpdate
from app.services.pipeline import run_extraction_pipeline

router = APIRouter(prefix="/memories", tags=["memories"])


def _to_response(m: PrismaMemory, tag_names: Optional[list[str]] = None) -> MemoryResponse:
    """Map Prisma Memory to API response. Pass tag_names when memory includes tags relation."""
    return MemoryResponse(
        id=m.id,
        userId=m.userId,
        type=m.type,
        title=m.title,
        summary=m.summary,
        extractedText=m.extractedText,
        sourceUrl=m.sourceUrl,
        contentHash=m.contentHash,
        status=m.status,
        createdAt=m.createdAt,
        updatedAt=m.updatedAt,
        tags=tag_names,
    )


@router.post("", response_model=MemoryResponse, status_code=201)
async def create_memory(
    body: MemoryCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    background_tasks: BackgroundTasks,
) -> MemoryResponse:
    """Create a new memory (owned by current user)."""
    memory = await PrismaMemory.prisma().create(
        data={
            "userId": current_user.id,
            "type": body.type,
            "contentHash": body.contentHash,
            "title": body.title,
            "summary": body.summary,
            "extractedText": body.extractedText,
            "sourceUrl": body.sourceUrl,
            "status": body.status,
        }
    )
    if body.sourceUrl and (body.sourceUrl.startswith("http://") or body.sourceUrl.startswith("https://")):
        from app.config import PROCESSING_ENABLED
        if PROCESSING_ENABLED:
            background_tasks.add_task(run_extraction_pipeline, memory.id)
    return _to_response(memory)


@router.get("", response_model=list[MemoryResponse])
async def list_memories(
    current_user: Annotated[User, Depends(get_current_user)],
    type: Optional[str] = Query(None, description="Filter by type (pdf, image, video, text, webpage)"),
    status: Optional[str] = Query(None, description="Filter by status"),
    skip: int = Query(0, ge=0),
    take: int = Query(20, ge=1, le=100),
) -> list[MemoryResponse]:
    """List current user's memories with optional filters and pagination."""
    where: dict = {"userId": current_user.id}
    if type is not None:
        where["type"] = type
    if status is not None:
        where["status"] = status
    memories = await PrismaMemory.prisma().find_many(
        where=where,
        skip=skip,
        take=take,
        order={"createdAt": "desc"},
    )
    return [_to_response(m) for m in memories]


@router.get("/{memory_id}", response_model=MemoryResponse)
async def get_memory(
    memory_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
) -> MemoryResponse:
    """Get a single memory by ID (must belong to current user). Includes tags."""
    memory = await PrismaMemory.prisma().find_unique(
        where={"id": memory_id},
        include={"tags": {"include": {"tag": True}}},
    )
    if memory is None or memory.userId != current_user.id:
        raise HTTPException(status_code=404, detail="Memory not found")
    tag_names = [mt.tag.name for mt in memory.tags] if memory.tags else []
    return _to_response(memory, tag_names=tag_names)


@router.patch("/{memory_id}", response_model=MemoryResponse)
async def update_memory(
    memory_id: str,
    body: MemoryUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
) -> MemoryResponse:
    """Update memory metadata (partial; must belong to current user)."""
    existing = await PrismaMemory.prisma().find_unique(where={"id": memory_id})
    if existing is None or existing.userId != current_user.id:
        raise HTTPException(status_code=404, detail="Memory not found")
    data = body.model_dump(exclude_unset=True)
    # Prisma uses camelCase matching the schema
    prisma_data = {}
    if "title" in data:
        prisma_data["title"] = data["title"]
    if "summary" in data:
        prisma_data["summary"] = data["summary"]
    if "extractedText" in data:
        prisma_data["extractedText"] = data["extractedText"]
    if "sourceUrl" in data:
        prisma_data["sourceUrl"] = data["sourceUrl"]
    if "status" in data:
        prisma_data["status"] = data["status"]
    memory = await PrismaMemory.prisma().update(
        where={"id": memory_id},
        data=prisma_data,
    )
    return _to_response(memory)


@router.post("/{memory_id}/process", status_code=202)
async def process_memory(
    memory_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    background_tasks: BackgroundTasks,
) -> dict:
    """
    Trigger AI extraction pipeline for a memory (PDF text, OCR, transcription, summary, tags).
    Runs in the background; memory status will move to 'processing' then 'ready' or 'failed'.
    """
    memory = await PrismaMemory.prisma().find_unique(where={"id": memory_id})
    if memory is None or memory.userId != current_user.id:
        raise HTTPException(status_code=404, detail="Memory not found")
    background_tasks.add_task(run_extraction_pipeline, memory_id)
    return {"message": "Processing started", "memoryId": memory_id}


def _url_to_storage_key(file_url: str) -> str | None:
    """Extract storage key from fileUrl for local or Supabase."""
    if file_url.startswith("/files/"):
        return file_url.removeprefix("/files/").lstrip("/")
    if "supabase" in file_url and "/object/public/" in file_url:
        parts = file_url.split("/object/public/")
        if len(parts) == 2:
            bucket_and_path = parts[1].split("?")[0]
            segments = bucket_and_path.split("/")
            if len(segments) > 1:
                return "/".join(segments[1:])
            return bucket_and_path
    return None


@router.delete("/{memory_id}", status_code=204)
async def delete_memory(
    memory_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    """Delete a memory and all related records (uploads, extractions, etc.)."""
    existing = await PrismaMemory.prisma().find_unique(
        where={"id": memory_id},
        include={"uploads": True},
    )
    if existing is None or existing.userId != current_user.id:
        raise HTTPException(status_code=404, detail="Memory not found")
    for upload in existing.uploads:
        key = _url_to_storage_key(upload.fileUrl)
        if key:
            try:
                await storage.delete(key)
            except Exception:
                pass
    await PrismaUpload.prisma().delete_many(where={"memoryId": memory_id})
    await Extraction.prisma().delete_many(where={"memoryId": memory_id})
    await Embedding.prisma().delete_many(where={"memoryId": memory_id})
    await MemoryTag.prisma().delete_many(where={"memoryId": memory_id})
    await SpaceMemory.prisma().delete_many(where={"memoryId": memory_id})
    await PrismaMemory.prisma().delete(where={"id": memory_id})
