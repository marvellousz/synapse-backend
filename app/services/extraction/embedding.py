"""
Embedding generation for semantic search using Google's Gemini API.

Converts text chunks into vector embeddings for similarity search.
"""

import asyncio
import logging
from typing import Optional

from app.config import GEMINI_API_KEY
from app.services.extraction.gemini_client import get_embedding_client

logger = logging.getLogger(__name__)

# Embedding model from Google (text-embedding-004 is deprecated; use gemini-embedding-001)
EMBEDDING_MODEL = "gemini-embedding-001"

# Cache for embeddings to avoid regenerating
_embedding_cache: dict[str, list[float]] = {}


def generate_embedding(text: str) -> Optional[list[float]]:
    """
    Generate an embedding vector for a text chunk using Gemini API.

    Args:
        text: Text chunk to embed

    Returns:
        List of floats representing the embedding vector, or None on failure
    """
    if not text or not text.strip():
        return None

    # Check cache
    cache_key = text.strip()
    if cache_key in _embedding_cache:
        return _embedding_cache[cache_key]

    client = get_embedding_client()
    if not client or not GEMINI_API_KEY:
        logger.warning("Gemini client not available for embeddings")
        return None

    try:
        from google import genai
        from google.genai import types

        # Generate embedding using Google's API (768 dims for compatibility with existing stored embeddings)
        response = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=text.strip(),
            config=types.EmbedContentConfig(output_dimensionality=768),
        )

        # Extract embedding from response (Gemini API returns ContentEmbedding objects)
        embedding = None
        
        if hasattr(response, 'embedding') and response.embedding:
            # Direct embedding attribute
            embedding = response.embedding
        elif hasattr(response, 'embeddings') and response.embeddings:
            # Embeddings list - extract values from ContentEmbedding object
            embedding_obj = response.embeddings[0] if response.embeddings else None
            if embedding_obj:
                # ContentEmbedding object has .values property with the vector
                if hasattr(embedding_obj, 'values'):
                    embedding = embedding_obj.values
                elif hasattr(embedding_obj, '__iter__'):
                    # Fallback: try to iterate if it's array-like
                    embedding = list(embedding_obj)
        
        if embedding:
            # Ensure embedding is a list
            if not isinstance(embedding, (list, tuple)):
                embedding = list(embedding) if hasattr(embedding, '__iter__') else None
            
            if embedding:
                # Cache the result
                _embedding_cache[cache_key] = embedding
                logger.debug("Generated embedding for %d-char text", len(text))
                return embedding

    except Exception as e:
        logger.error("Failed to generate embedding: %s", e)
        return None

    return None


async def generate_embedding_async(text: str) -> Optional[list[float]]:
    """
    Async wrapper for embedding generation.
    Runs in thread pool to avoid blocking.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, generate_embedding, text)


def batch_generate_embeddings(texts: list[str]) -> list[Optional[list[float]]]:
    """
    Generate embeddings for multiple text chunks.

    Args:
        texts: List of text chunks

    Returns:
        List of embedding vectors (or None for failed items)
    """
    embeddings = []
    for text in texts:
        embedding = generate_embedding(text)
        embeddings.append(embedding)

    successful = sum(1 for e in embeddings if e is not None)
    logger.info("Generated %d/%d embeddings", successful, len(texts))
    return embeddings


async def batch_generate_embeddings_async(texts: list[str]) -> list[Optional[list[float]]]:
    """
    Async batch embedding generation.
    Generates embeddings concurrently with rate limiting.
    """
    # Generate in parallel but with small delays to respect API limits
    embeddings = []
    for i, text in enumerate(texts):
        if i > 0 and i % 5 == 0:
            await asyncio.sleep(0.5)  # Rate limiting: small delay every 5 chunks

        embedding = await generate_embedding_async(text)
        embeddings.append(embedding)

    successful = sum(1 for e in embeddings if e is not None)
    logger.info("Generated %d/%d embeddings async", successful, len(texts))
    return embeddings


def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """
    Calculate cosine similarity between two vectors.

    Args:
        vec1: First embedding vector
        vec2: Second embedding vector

    Returns:
        Similarity score between 0 and 1 (1 = identical, 0 = orthogonal)
    """
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0

    # Dot product
    dot_product = sum(a * b for a, b in zip(vec1, vec2))

    # Magnitudes
    mag1 = sum(a * a for a in vec1) ** 0.5
    mag2 = sum(b * b for b in vec2) ** 0.5

    if mag1 == 0 or mag2 == 0:
        return 0.0

    similarity = dot_product / (mag1 * mag2)
    # Normalize to [0, 1] range (cosine gives [-1, 1])
    return (similarity + 1) / 2


def find_similar_embeddings(
    query_embedding: list[float],
    candidate_embeddings: list[dict],
    top_k: int = 10,
    threshold: float = 0.5,
) -> list[dict]:
    """
    Find embeddings most similar to query using cosine similarity.

    Args:
        query_embedding: Embedding vector for the query
        candidate_embeddings: List of dicts with keys 'id', 'embedding', 'text', 'memoryId'
        top_k: Number of results to return
        threshold: Minimum similarity score (0-1)

    Returns:
        List of dicts with keys 'id', 'memoryId', 'text', 'similarity', 'chunkIndex', sorted by similarity
    """
    if not query_embedding or not candidate_embeddings:
        return []

    scored = []
    for candidate in candidate_embeddings:
        if "embedding" not in candidate or not candidate["embedding"]:
            continue

        similarity = cosine_similarity(query_embedding, candidate["embedding"])
        logger.debug("Similarity for candidate %s: %.4f (threshold: %.2f)", 
                    candidate.get("id", "unknown")[:8], similarity, threshold)
        
        if similarity >= threshold:
            scored.append(
                {
                    "id": candidate.get("id"),
                    "memoryId": candidate.get("memoryId"),
                    "text": candidate.get("text", ""),
                    "similarity": similarity,
                    "chunkIndex": candidate.get("chunkIndex"),
                }
            )

    # Sort by similarity (descending)
    scored.sort(key=lambda x: x["similarity"], reverse=True)
    logger.info("Found %d similar embeddings above threshold", len(scored))

    return scored[:top_k]


def clear_embedding_cache():
    """Clear the embedding cache (useful for testing or memory cleanup)."""
    global _embedding_cache
    _embedding_cache.clear()
    logger.info("Embedding cache cleared")
