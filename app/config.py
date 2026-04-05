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
STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "supabase")

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
# Gemini guidance:
# - Inline media in requests: keep small (video-understanding docs show <20 MB)
# - Files API upload (free tier): up to 2 GB per file
GEMINI_INLINE_VIDEO_MAX_BYTES = int(os.getenv("GEMINI_INLINE_VIDEO_MAX_BYTES", 20 * 1024 * 1024))
GEMINI_FILES_API_MAX_FILE_BYTES = int(os.getenv("GEMINI_FILES_API_MAX_FILE_BYTES", 2 * 1024 * 1024 * 1024))
# Keep a conservative default here because current upload endpoint reads file bytes into memory.
# Can be increased via env var (still capped by GEMINI_FILES_API_MAX_FILE_BYTES in validation).
MAX_FILE_SIZE_VIDEO = int(os.getenv("MAX_FILE_SIZE_VIDEO", 50 * 1024 * 1024))  # 50 MB
MAX_FILE_SIZE_TEXT = int(os.getenv("MAX_FILE_SIZE_TEXT", 1 * 1024 * 1024))  # 1 MB

# Base URL for serving local files (e.g. http://localhost:8000/files/)
LOCAL_FILES_BASE_URL = os.getenv("LOCAL_FILES_BASE_URL", "").rstrip("/")

# JWT (auth)
JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "10080"))  # 7 days

# Frontend URL for email action links
FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "http://localhost:3000").rstrip("/")

# Extra CORS origins (comma-separated), e.g. preview deploys or staging frontends
CORS_EXTRA_ORIGINS = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "").split(",")
    if o.strip()
]

# Resend email settings
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "").strip()
RESEND_FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL", "onboarding@resend.dev").strip()

# AI extraction (Phase 3) — Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
PROCESSING_ENABLED = os.getenv("PROCESSING_ENABLED", "true").lower() in ("true", "1", "yes")
# Max text length to send to LLM for summary/tags (chars)
EXTRACTION_SUMMARY_MAX_CHARS = int(os.getenv("EXTRACTION_SUMMARY_MAX_CHARS", "12000"))

# OCR: optional explicit path to Tesseract binary (useful on Windows)
TESSERACT_CMD = os.getenv("TESSERACT_CMD", "").strip()

# YouTube transcript (youtube-transcript-api): cloud IPs are often blocked; use a rotating residential proxy.
# Option A — Webshare (see library README "Working around IP bans"):
YOUTUBE_TRANSCRIPT_WEBSHARE_USERNAME = os.getenv("YOUTUBE_TRANSCRIPT_WEBSHARE_USERNAME", "").strip()
YOUTUBE_TRANSCRIPT_WEBSHARE_PASSWORD = os.getenv("YOUTUBE_TRANSCRIPT_WEBSHARE_PASSWORD", "").strip()
# Comma-separated ISO country codes, e.g. "de,us" (optional)
_raw_yt_loc = os.getenv("YOUTUBE_TRANSCRIPT_WEBSHARE_FILTER_LOCATIONS", "").strip()
YOUTUBE_TRANSCRIPT_WEBSHARE_FILTER_LOCATIONS = [
    x.strip().lower() for x in _raw_yt_loc.split(",") if x.strip()
]
# Option B — generic HTTP/HTTPS proxy URLs (e.g. http://user:pass@host:port)
YOUTUBE_TRANSCRIPT_HTTP_PROXY = os.getenv("YOUTUBE_TRANSCRIPT_HTTP_PROXY", "").strip()
YOUTUBE_TRANSCRIPT_HTTPS_PROXY = os.getenv("YOUTUBE_TRANSCRIPT_HTTPS_PROXY", "").strip()
