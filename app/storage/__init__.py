# Storage backends

from app.config import STORAGE_BACKEND
from app.storage.base import StorageBackend

if STORAGE_BACKEND == "supabase":
    from app.storage.supabase_storage import SupabaseStorage

    storage: StorageBackend = SupabaseStorage()
else:
    from app.storage.local_storage import LocalStorage

    storage: StorageBackend = LocalStorage()

__all__ = ["storage", "StorageBackend"]
