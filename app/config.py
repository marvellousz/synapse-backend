"""Application configuration."""

import os
from pathlib import Path

# Load .env so GEMINI_API_KEY and other vars are available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Storage: "local" or "supabase"
STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local")

# Local storage path (used when STORAGE_BACKEND=local)
LOCAL_STORAGE_PATH = Path(os.getenv("LOCAL_STORAGE_PATH", "uploads")).resolve()
LOCAL_STORAGE_PATH.mkdir(parents=True, exist_ok=True)

# Supabase (used when STORAGE_BACKEND=supabase)
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_BUCKET = os.getenv("SUPABASE_UPLOAD_BUCKET", "uploads")

# File size limits (bytes)
MAX_FILE_SIZE_PDF = int(os.getenv("MAX_FILE_SIZE_PDF", 20 * 1024 * 1024))  # 20 MB
MAX_FILE_SIZE_IMAGE = int(os.getenv("MAX_FILE_SIZE_IMAGE", 10 * 1024 * 1024))  # 10 MB
MAX_FILE_SIZE_VIDEO = int(os.getenv("MAX_FILE_SIZE_VIDEO", 50 * 1024 * 1024))  # 50 MB
MAX_FILE_SIZE_TEXT = int(os.getenv("MAX_FILE_SIZE_TEXT", 1 * 1024 * 1024))  # 1 MB

# Base URL for serving local files (e.g. http://localhost:8000/files/)
LOCAL_FILES_BASE_URL = os.getenv("LOCAL_FILES_BASE_URL", "").rstrip("/")

# JWT (auth)
JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "10080"))  # 7 days

# AI extraction (Phase 3) — Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
PROCESSING_ENABLED = os.getenv("PROCESSING_ENABLED", "true").lower() in ("true", "1", "yes")
# Max text length to send to LLM for summary/tags (chars)
EXTRACTION_SUMMARY_MAX_CHARS = int(os.getenv("EXTRACTION_SUMMARY_MAX_CHARS", "12000"))
