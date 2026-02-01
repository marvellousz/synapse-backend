"""Abstract storage backend."""

from abc import ABC, abstractmethod


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
        """Build storage key: memory_id/unique_id_filename to avoid collisions."""
        safe_name = "".join(c for c in filename if c.isalnum() or c in "._-")[:64]
        return f"{memory_id}/{unique_id}_{safe_name}"
