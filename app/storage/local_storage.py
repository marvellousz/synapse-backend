"""Local filesystem storage."""

import aiofiles
from pathlib import Path

from app.config import LOCAL_FILES_BASE_URL, LOCAL_STORAGE_PATH
from app.storage.base import StorageBackend


class LocalStorage(StorageBackend):
    """Store files on local disk. fileUrl is a path like /files/memory_id/unique_name."""

    def __init__(self) -> None:
        self.root = Path(LOCAL_STORAGE_PATH).resolve()

    def _path(self, key: str) -> Path:
        key = key.lstrip("/").replace("..", "")
        return (self.root / key).resolve()

    def _ensure_safe_key(self, key: str) -> None:
        """Prevent path traversal."""
        key = key.lstrip("/").replace("..", "")
        resolved = (self.root / key).resolve()
        if not str(resolved).startswith(str(self.root)):
            raise ValueError("Invalid storage key")

    async def upload(
        self,
        content: bytes,
        key: str,
        content_type: str | None = None,
    ) -> str:
        key = key.lstrip("/").replace("..", "")
        self._ensure_safe_key(key)
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(path, "wb") as f:
            await f.write(content)
        if LOCAL_FILES_BASE_URL:
            return f"{LOCAL_FILES_BASE_URL}/{key}"
        return f"/files/{key}"

    async def delete(self, key: str) -> None:
        key = key.lstrip("/").replace("..", "")
        self._ensure_safe_key(key)
        path = self._path(key)
        if path.exists():
            path.unlink()
