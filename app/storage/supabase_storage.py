"""Supabase Storage backend."""

import logging

from storage3.exceptions import StorageApiError
from supabase import create_client

from app.config import SUPABASE_BUCKET, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_URL
from app.storage.base import StorageBackend


logger = logging.getLogger(__name__)


class SupabaseStorage(StorageBackend):
    """Store files in Supabase Storage bucket. Returns public URL."""

    def __init__(self) -> None:
        if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set when STORAGE_BACKEND=supabase"
            )
        self.client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
        self.bucket = SUPABASE_BUCKET
        self._ensure_bucket_exists()

    def _ensure_bucket_exists(self) -> None:
        """Ensure configured bucket exists; create it when missing."""
        try:
            self.client.storage.get_bucket(self.bucket)
        except StorageApiError as e:
            # Supabase returns statusCode 404 when the bucket does not exist.
            if str(getattr(e, "status", "")) == "404":
                logger.warning("Supabase bucket '%s' not found, creating it", self.bucket)
                try:
                    self.client.storage.create_bucket(
                        self.bucket,
                        options={"public": True},
                    )
                except StorageApiError as create_err:
                    # If another process created it meanwhile, continue.
                    if str(getattr(create_err, "status", "")) != "409":
                        raise
                return
            raise

    async def upload(
        self,
        content: bytes,
        key: str,
        content_type: str | None = None,
    ) -> str:
        opts: dict = {}
        if content_type:
            opts["contentType"] = content_type
        try:
            self.client.storage.from_(self.bucket).upload(key, content, opts)
        except StorageApiError as e:
            raise RuntimeError(f"Supabase upload failed for bucket '{self.bucket}': {e}") from e
        return self.client.storage.from_(self.bucket).get_public_url(key)

    async def delete(self, key: str) -> None:
        try:
            self.client.storage.from_(self.bucket).remove([key])
        except StorageApiError as e:
            raise RuntimeError(f"Supabase delete failed for bucket '{self.bucket}': {e}") from e
