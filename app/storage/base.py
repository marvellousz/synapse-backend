"""Abstract storage backend."""

from abc import ABC, abstractmethod
from datetime import datetime, timezone


class StorageBackend(ABC):
    """Interface for file storage (local or cloud)."""

    @abstractmethod
    async def upload(
        self,
        content: bytes,
        key: str,
        content_type: str | None = None,
    ) -> str:
        """
        Store file and return a URL or path used to reference it.
        key is a unique path like memory_id/filename or memory_id/uuid.ext.
        """
        ...

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Remove file at key. Key is the same as returned from upload."""
        ...

    def key_for_memory(self, memory_id: str, filename: str, unique_id: str) -> str:
        """Build legacy storage key: memory_id/unique_id_filename to avoid collisions."""
        safe_name = "".join(c for c in filename if c.isalnum() or c in "._-")[:64]
        return f"{memory_id}/{unique_id}_{safe_name}"

    def key_for_user_memory(
        self,
        user_id: str,
        memory_id: str,
        category: str | None,
        filename: str,
        unique_id: str,
    ) -> str:
        """Build user-scoped storage key with category/date path segments."""
        safe_name = "".join(c for c in filename if c.isalnum() or c in "._-")[:64]
        safe_user = "".join(c for c in user_id if c.isalnum() or c in "-_")[:64]
        safe_memory = "".join(c for c in memory_id if c.isalnum() or c in "-_")[:64]
        safe_category = "".join(c for c in (category or "") if c.isalnum() or c in "-_").lower()[:64]
        if not safe_category:
            safe_category = "uncategorized"
        date_folder = datetime.now(timezone.utc).strftime("%Y/%m/%d")
        return f"{safe_user}/{safe_memory}/{safe_category}/{date_folder}/{unique_id}_{safe_name}"
