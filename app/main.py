from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from prisma import Prisma

from app.config import CORS_EXTRA_ORIGINS, LOCAL_STORAGE_PATH, STORAGE_BACKEND
from app.routers import auth, chat, chats, memories, uploads, search

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Set specific loggers to DEBUG for search functionality
logging.getLogger('app.services.search_service').setLevel(logging.DEBUG)
logging.getLogger('app.services.extraction.embedding').setLevel(logging.DEBUG)

prisma = Prisma(auto_register=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage Prisma connection lifecycle."""
    # Don't crash the whole service if the DB/query engine isn't reachable at startup.
    # This keeps OPTIONS/preflight working (CORS headers) so the frontend can surface
    # meaningful API errors instead of "service failed to respond".
    try:
        await prisma.connect()
        app.state.prisma_connected = True
    except Exception as e:
        app.state.prisma_connected = False
        logging.getLogger(__name__).exception("Prisma connect failed; starting app anyway.")
    yield
    if getattr(app.state, "prisma_connected", False) and prisma.is_connected():
        await prisma.disconnect()


app = FastAPI(
    title="Synapse API",
    description="Personal second-brain knowledge management system",
    version="0.1.0",
    lifespan=lifespan,
)

_DEFAULT_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://synapse-frontend-gamma.vercel.app",
]
# Dedupe while preserving order (env CORS_ORIGINS appended for previews/staging)
_cors_origins = list(dict.fromkeys(_DEFAULT_CORS_ORIGINS + CORS_EXTRA_ORIGINS))

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_origin_regex=r"^chrome-extension://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(memories.router)
app.include_router(uploads.router)
app.include_router(search.router)
app.include_router(chat.router)
app.include_router(chats.router)


@app.get("/")
async def root():
    return {"message": "Synapse API", "version": "0.1.0"}


# Serve local uploads when STORAGE_BACKEND=local (fileUrl is /files/...)
if STORAGE_BACKEND == "local":

    @app.get("/files/{path:path}")
    async def serve_upload(path: str):
        """Serve files from local uploads directory. Path must be under uploads root."""
        path = path.lstrip("/").replace("..", "")
        full_path = (LOCAL_STORAGE_PATH / path).resolve()
        if not str(full_path).startswith(str(LOCAL_STORAGE_PATH.resolve())):
            return PlainTextResponse("Forbidden", status_code=403)
        if not full_path.is_file():
            return PlainTextResponse("Not Found", status_code=404)
        return FileResponse(full_path)