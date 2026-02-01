"""File validation and type detection for uploads."""

import mimetypes
from typing import Literal

from app.config import (
    MAX_FILE_SIZE_IMAGE,
    MAX_FILE_SIZE_PDF,
    MAX_FILE_SIZE_TEXT,
    MAX_FILE_SIZE_VIDEO,
)

# Schema file types
UploadFileType = Literal["pdf", "image", "video", "text"]

# Allowed MIME types and extensions -> schema fileType
MIME_TO_FILETYPE: dict[str, UploadFileType] = {
    "application/pdf": "pdf",
    "image/jpeg": "image",
    "image/png": "image",
    "image/gif": "image",
    "image/webp": "image",
    "image/heic": "image",
    "video/mp4": "video",
    "video/webm": "video",
    "video/quicktime": "video",
    "video/x-msvideo": "video",
    "text/plain": "text",
    "text/markdown": "text",
    "text/csv": "text",
    "application/json": "text",
}

EXT_TO_FILETYPE: dict[str, UploadFileType] = {
    ".pdf": "pdf",
    ".jpg": "image",
    ".jpeg": "image",
    ".png": "image",
    ".gif": "image",
    ".webp": "image",
    ".heic": "image",
    ".mp4": "video",
    ".webm": "video",
    ".mov": "video",
    ".avi": "video",
    ".txt": "text",
    ".md": "text",
    ".csv": "text",
    ".json": "text",
}

MAX_SIZE_BY_TYPE: dict[UploadFileType, int] = {
    "pdf": MAX_FILE_SIZE_PDF,
    "image": MAX_FILE_SIZE_IMAGE,
    "video": MAX_FILE_SIZE_VIDEO,
    "text": MAX_FILE_SIZE_TEXT,
}


def detect_file_type(filename: str, content_type: str | None) -> UploadFileType | None:
    """Determine schema fileType from filename and optional content_type."""
    if content_type:
        base_type = content_type.split(";")[0].strip().lower()
        if base_type in MIME_TO_FILETYPE:
            return MIME_TO_FILETYPE[base_type]
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return EXT_TO_FILETYPE.get(ext)


def get_max_size(file_type: UploadFileType) -> int:
    """Return max allowed size in bytes for the given file type."""
    return MAX_SIZE_BY_TYPE.get(file_type, MAX_FILE_SIZE_TEXT)


def validate_upload(
    filename: str,
    content_type: str | None,
    size: int,
) -> tuple[UploadFileType | None, str | None]:
    """
    Validate file and return (file_type, error_message).
    If valid, error_message is None.
    """
    file_type = detect_file_type(filename, content_type)
    if not file_type:
        return None, (
            "Unsupported file type. Allowed: PDF, images (JPEG/PNG/GIF/WebP/HEIC), "
            "videos (MP4/WebM/MOV/AVI), text (TXT/MD/CSV/JSON)."
        )
    max_size = get_max_size(file_type)
    if size > max_size:
        return file_type, f"File too large. Max size for {file_type}: {max_size // (1024*1024)} MB"
    return file_type, None
