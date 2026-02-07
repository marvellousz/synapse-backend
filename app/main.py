from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from prisma import Prisma

from app.config import LOCAL_STORAGE_PATH, STORAGE_BACKEND
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
    await prisma.connect()
    yield
    if prisma.is_connected():
        await prisma.disconnect()


app = FastAPI(
    title="Synapse API",
    description="Personal second-brain knowledge management system",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
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