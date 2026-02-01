"""Search API endpoints for semantic and keyword search."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from prisma.models import User

from app.core.auth import get_current_user
from app.services.search_service import (
    get_related_memories,
    hybrid_search,
    keyword_search,
    search_by_content,
)

router = APIRouter(prefix="/api/search", tags=["search"])


# Request/Response models
class SearchQuery(BaseModel):
    """Semantic/hybrid search query."""

    query: str
    limit: int = 10
    contentType: str | None = None


class SearchResult(BaseModel):
    """Search result with matching chunks."""

    memoryId: str
    title: str
    contentType: str
    summary: str
    sourceUrl: str | None = None
    createdAt: str
    matches: list[dict] | None = None
    semanticScore: float | None = None
    keywordScore: float | None = None
    combinedScore: float | None = None


class KeywordSearchQuery(BaseModel):
    """Keyword search query."""

    keywords: str
    limit: int = 10
    contentType: str | None = None


class RelatedMemoriesResponse(BaseModel):
    """Related memories result."""

    memoryId: str
    title: str
    similarity: float
    type: str


@router.post("/semantic")
async def semantic_search(
    query: SearchQuery,
    current_user: User = Depends(get_current_user),
) -> list[SearchResult]:
    """
    Step 6: Perform semantic similarity search.

    Converts user's natural language query into an embedding and finds
    the most semantically similar chunks across all memories.

    Example query:
    - "Find that quote from my handwritten note"
    - "What did I learn about machine learning?"
    - "Show me notes about productivity tips"

    Returns chunks ranked by semantic similarity.
    """
    if not query.query or not query.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    results = await search_by_content(
        query=query.query,
        user_id=current_user.id,
        limit=query.limit,
        content_type_filter=query.contentType,
    )
    
    # Add semantic score only (no keyword score for semantic search)
    for result in results:
        # Remove keyword and combined scores from response
        result.pop("keywordScore", None)
        result.pop("combinedScore", None)

    return results


@router.post("/keyword")
async def keyword_search_endpoint(
    query: KeywordSearchQuery,
    current_user: User = Depends(get_current_user),
) -> list[SearchResult]:
    """
    Perform traditional keyword-based search.

    Searches for exact matches or partial matches in:
    - Memory titles
    - Summaries
    - Extracted text
    - Chunk content

    Useful when users know specific words or phrases.
    """
    if not query.keywords or not query.keywords.strip():
        raise HTTPException(status_code=400, detail="Keywords cannot be empty")

    results = await keyword_search(
        query=query.keywords,
        user_id=current_user.id,
        limit=query.limit,
        content_type_filter=query.contentType,
    )
    
    # keywordScore is already calculated in keyword_search, just remove other scores
    for result in results:
        # Remove semantic and combined scores from response
        result.pop("semanticScore", None)
        result.pop("combinedScore", None)

    return results


@router.post("/hybrid")
async def hybrid_search_endpoint(
    query: SearchQuery,
    semantic_weight: float = Query(0.7, ge=0, le=1),
    keyword_weight: float = Query(0.3, ge=0, le=1),
    current_user: User = Depends(get_current_user),
) -> list[SearchResult]:
    """
    Step 7: Perform hybrid search combining semantic + keyword matching.

    Merges results from both semantic and keyword search, reranking by
    combined score. This prevents:
    - Semantic misses when keywords differ
    - Keyword-only inaccuracy when meaning matters
    - Vague matches that aren't relevant

    Query parameters:
    - semantic_weight: How much to weight semantic similarity (default 0.7)
    - keyword_weight: How much to weight keyword matches (default 0.3)

    Returns results ranked by combined relevance.
    """
    if not query.query or not query.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    results = await hybrid_search(
        query=query.query,
        user_id=current_user.id,
        limit=query.limit,
        content_type_filter=query.contentType,
        semantic_weight=semantic_weight,
        keyword_weight=keyword_weight,
    )

    return results


@router.get("/related/{memory_id}")
async def get_related(
    memory_id: str,
    limit: int = Query(5, ge=1, le=20),
    current_user: User = Depends(get_current_user),
) -> list[RelatedMemoriesResponse]:
    """
    Find memories semantically similar to a given memory.

    Useful for:
    - "Related memories" sidebar in detail view
    - Browsing by concept/topic
    - Knowledge graph visualization
    - Discovering connections between notes

    Returns:
    - List of related memories with similarity scores
    """
    results = await get_related_memories(
        memory_id=memory_id,
        user_id=current_user.id,
        limit=limit,
    )

    return results


@router.get("/health")
async def search_health() -> dict:
    """Health check for search service."""
    return {"status": "ok", "service": "semantic_search"}
