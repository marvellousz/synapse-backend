"""Upload API: store files and link to memories."""

import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile

from prisma.models import Memory as PrismaMemory
from prisma.models import Upload as PrismaUpload
from prisma.models import User

from app.config import PROCESSING_ENABLED
from app.core.auth import get_current_user
from app.core.upload_validation import validate_upload
from app.schemas.upload import UploadResponse
from app.services.pipeline import run_extraction_pipeline
from app.storage import storage

router = APIRouter(tags=["uploads"])


def _to_response(u: PrismaUpload) -> UploadResponse:
    return UploadResponse(
        id=u.id,
        memoryId=u.memoryId,
        fileUrl=u.fileUrl,
        fileType=u.fileType,
        mimeType=u.mimeType,
        fileSize=u.fileSize,
        createdAt=u.createdAt,
    )


@router.post(
    "/memories/{memory_id}/uploads",
    response_model=list[UploadResponse],
    status_code=201,
)
async def upload_files(
    memory_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
) -> list[UploadResponse]:
    """
    Upload one or more files and link them to a memory (memory must belong to current user).
    Allowed: PDF, images (JPEG/PNG/GIF/WebP/HEIC), videos (MP4/WebM/MOV/AVI), text (TXT/MD/CSV/JSON).
    """
    memory = await PrismaMemory.prisma().find_unique(where={"id": memory_id})
    if not memory or memory.userId != current_user.id:
        raise HTTPException(status_code=404, detail="Memory not found")
    if not files:
        raise HTTPException(status_code=400, detail="At least one file is required")

    results: list[UploadResponse] = []
    for upload_file in files:
        if not upload_file.filename:
            raise HTTPException(status_code=400, detail="Filename is required")
        content = await upload_file.read()
        size = len(content)
        content_type = upload_file.content_type
        file_type, err = validate_upload(upload_file.filename, content_type, size)
        if err or file_type is None:
            raise HTTPException(status_code=400, detail=err or "Unsupported file type")
        unique_id = uuid.uuid4().hex[:12]
        key = storage.key_for_memory(memory_id, upload_file.filename, unique_id)
        file_url = await storage.upload(content, key, content_type=content_type)
        upload_record = await PrismaUpload.prisma().create(
            data={
                "memoryId": memory_id,
                "fileUrl": file_url,
                "fileType": file_type,
                "mimeType": content_type,
                "fileSize": size,
            }
        )
        results.append(_to_response(upload_record))
    if PROCESSING_ENABLED and results:
        background_tasks.add_task(run_extraction_pipeline, memory_id)
    return results


@router.get("/memories/{memory_id}/uploads", response_model=list[UploadResponse])
async def list_uploads(
    memory_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[UploadResponse]:
    """List all uploads for a memory (memory must belong to current user)."""
    memory = await PrismaMemory.prisma().find_unique(where={"id": memory_id})
    if not memory or memory.userId != current_user.id:
        raise HTTPException(status_code=404, detail="Memory not found")
    uploads = await PrismaUpload.prisma().find_many(
        where={"memoryId": memory_id},
        order={"createdAt": "desc"},
    )
    return [_to_response(u) for u in uploads]


@router.get("/uploads/{upload_id}", response_model=UploadResponse)
async def get_upload(
    upload_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
) -> UploadResponse:
    """Get a single upload by ID (memory must belong to current user)."""
    upload = await PrismaUpload.prisma().find_unique(where={"id": upload_id}, include={"memory": True})
    if not upload or not upload.memory or upload.memory.userId != current_user.id:
        raise HTTPException(status_code=404, detail="Upload not found")
    return _to_response(upload)


@router.delete("/uploads/{upload_id}", status_code=204)
async def delete_upload(
    upload_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    """Delete an upload record and remove the file from storage (memory must belong to current user)."""
    upload = await PrismaUpload.prisma().find_unique(where={"id": upload_id}, include={"memory": True})
    if not upload or not upload.memory or upload.memory.userId != current_user.id:
        raise HTTPException(status_code=404, detail="Upload not found")
    file_url = upload.fileUrl
    key = _url_to_storage_key(file_url)
    if key:
        await storage.delete(key)
    await PrismaUpload.prisma().delete(where={"id": upload_id})


def _url_to_storage_key(file_url: str) -> str | None:
    """Extract storage key from fileUrl for local (/files/...) or Supabase (full URL)."""
    if file_url.startswith("/files/"):
        return file_url.removeprefix("/files/").lstrip("/")
    if "supabase" in file_url and "/object/public/" in file_url:
        parts = file_url.split("/object/public/")
        if len(parts) == 2:
            bucket_and_path = parts[1].split("?")[0]
            segments = bucket_and_path.split("/")
            if len(segments) > 1:
                return "/".join(segments[1:])  # path without bucket name
            return bucket_and_path
    return None
