"""Fetch file bytes from storage (local path or URL)."""

from pathlib import Path

import httpx

from app.config import LOCAL_STORAGE_PATH


async def fetch_file_bytes(file_url: str) -> bytes:
    """
    Return file content as bytes.
    - If file_url starts with http(s), fetch via HTTP.
    - If file_url is /files/..., read from local storage path.
    """
    file_url = file_url.strip()
    if file_url.startswith("http://") or file_url.startswith("https://"):
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(file_url)
            resp.raise_for_status()
            return resp.content
    if file_url.startswith("/files/"):
        key = file_url.removeprefix("/files/").lstrip("/").replace("..", "")
        path = (LOCAL_STORAGE_PATH / key).resolve()
        if not str(path).startswith(str(LOCAL_STORAGE_PATH.resolve())):
            raise ValueError("Invalid file path")
        return path.read_bytes()
    raise ValueError(f"Unsupported file_url format: {file_url[:50]}")
