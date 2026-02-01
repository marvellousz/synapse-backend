"""Supabase Storage backend."""

from supabase import create_client

from app.config import SUPABASE_BUCKET, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_URL
from app.storage.base import StorageBackend


class SupabaseStorage(StorageBackend):
    """Store files in Supabase Storage bucket. Returns public URL."""

    def __init__(self) -> None:
        if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set when STORAGE_BACKEND=supabase"
            )
        self.client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
        self.bucket = SUPABASE_BUCKET

    async def upload(
        self,
        content: bytes,
        key: str,
        content_type: str | None = None,
    ) -> str:
        opts: dict = {}
        if content_type:
            opts["contentType"] = content_type
        self.client.storage.from_(self.bucket).upload(key, content, opts)
        return self.client.storage.from_(self.bucket).get_public_url(key)

    async def delete(self, key: str) -> None:
        self.client.storage.from_(self.bucket).remove([key])
