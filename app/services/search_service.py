"""
Semantic search engine combining embeddings with keyword matching.

Performs Step 5-7 of Phase 4: Query processing, similarity search, and hybrid ranking.
"""

import base64
import json
import logging
import re
from typing import Optional

from prisma.models import Embedding as PrismaEmbedding
from prisma.models import Memory as PrismaMemory

from app.services.extraction.embedding import (
    generate_embedding,
    find_similar_embeddings,
)

logger = logging.getLogger(__name__)


def _deserialize_vector(raw_value: object) -> Optional[list[float]]:
    """Deserialize embedding vector from stored format."""
    if raw_value is None:
        return None

    # If it's already a list or tuple, return as-is
    if isinstance(raw_value, (list, tuple)):
        return list(raw_value)

    # If it's a string, parse as JSON
    if isinstance(raw_value, str):
        try:
            return json.loads(raw_value)
        except json.JSONDecodeError:
            return None

    # If it's bytes, try to decode and parse as JSON
    if isinstance(raw_value, bytes):
        try:
            return json.loads(raw_value.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

    # Try to iterate if it's an iterable object
    if hasattr(raw_value, "__iter__"):
        try:
            return list(raw_value)
        except Exception:
            return None

    return None


async def search_by_content(
    query: str,
    user_id: str,
    limit: int = 10,
    content_type_filter: Optional[str] = None,
) -> list[dict]:
    """
    Perform semantic search across user's memories.

    Step 5: Process the user query into an embedding
    Step 6: Perform semantic similarity search
    Step 8: Return contextual results

    Args:
        query: Natural language search query
        user_id: User ID to filter results
        limit: Maximum number of results to return
        content_type_filter: Optional filter by content type (pdf, image, video, text, webpage)

    Returns:
        List of result dicts with keys:
            - memoryId: Memory ID
            - title: Memory title
            - contentType: Type of content
            - matchingChunk: The chunk that matched
            - chunkIndex: Position in document
            - similarity: Score (0-1)
            - summary: Memory summary
            - sourceUrl: Source URL if applicable
    """
    if not query or not query.strip():
        return []

    try:
        # Step 5: Convert query to embedding
        query_embedding = generate_embedding(query)
        if not query_embedding:
            logger.warning("Failed to generate query embedding for: %s", query)
            return []
        
        logger.debug("Generated query embedding with %d dimensions", len(query_embedding))

        # Get all embeddings for user's memories
        # We need to join through Memory to get user_id filter
        user_memories = await PrismaMemory.prisma().find_many(
            where={"userId": user_id},
            include={"embeddings": True},
        )

        if not user_memories:
            logger.debug("No memories found for user %s", user_id)
            return []
        
        logger.debug("Found %d memories for user %s", len(user_memories), user_id)

        # Collect all embeddings from user's memories
        all_embeddings = []
        memory_map = {}

        for memory in user_memories:
            # Apply content type filter if specified
            if content_type_filter and memory.type != content_type_filter:
                continue

            memory_map[memory.id] = memory

            if hasattr(memory, "embeddings") and memory.embeddings:
                logger.debug("Memory %s has %d embeddings", memory.id, len(memory.embeddings))
                for emb in memory.embeddings:
                    try:
                        vector = _deserialize_vector(emb.vector)
                        if not vector:
                            logger.warning("Failed to deserialize embedding %s (returned None)", emb.id)
                            continue
                        
                        logger.debug("Deserialized embedding %s with %d dimensions", emb.id, len(vector))

                        all_embeddings.append(
                            {
                                "id": emb.id,
                                "memoryId": emb.memoryId,
                                "embedding": vector,
                                "text": emb.chunkText,
                                "chunkIndex": emb.chunkIndex,
                            }
                        )
                    except Exception as e:
                        logger.warning("Failed to deserialize embedding %s: %s", emb.id, e)

        if not all_embeddings:
            logger.warning("No embeddings found for user %s after deserialization", user_id)
            return []
        
        logger.info("Loaded %d embeddings for semantic search", len(all_embeddings))

        # Step 6: Find similar embeddings
        similar = find_similar_embeddings(query_embedding, all_embeddings, top_k=limit * 2)

        if not similar:
            logger.warning("No similar embeddings found for query: %s (threshold may be too high)", query)
            return []
        
        logger.info("Found %d similar embeddings for query", len(similar))

        # Step 8: Format results with context
        results_by_memory = {}
        for match in similar[:limit]:
            memory_id = match.get("memoryId")

            if not memory_id:
                logger.warning("Match missing memoryId: %s", match)
                continue

            # Find the corresponding memory object
            memory = None
            for mem in user_memories:
                if mem.id == memory_id:
                    memory = mem
                    break

            if not memory:
                logger.warning("Memory %s not found for match", memory_id)
                continue

            if memory_id not in results_by_memory:
                results_by_memory[memory_id] = {
                    "memoryId": memory.id,
                    "title": memory.title or "Untitled",
                    "contentType": memory.type,
                    "summary": memory.summary or "",
                    "sourceUrl": memory.sourceUrl or "",
                    "createdAt": memory.createdAt.isoformat() if hasattr(memory.createdAt, "isoformat") else str(memory.createdAt),
                    "matches": [],
                }

            results_by_memory[memory_id]["matches"].append(
                {
                    "chunk": match["text"],
                    "chunkIndex": match.get("chunkIndex", 0),
                    "similarity": match["similarity"],
                }
            )

        # Convert to list and take top results
        results = list(results_by_memory.values())
        # Sort by best match similarity
        for result in results:
            best_sim = max((m["similarity"] for m in result["matches"]), default=0)
            result["bestSimilarity"] = best_sim
            result["semanticScore"] = best_sim  # For frontend compatibility
            result["combinedScore"] = best_sim  # For frontend compatibility
        results.sort(key=lambda x: x["bestSimilarity"], reverse=True)

        logger.info("Found %d memories matching query: %s", len(results), query)
        return results[:limit]

    except Exception as e:
        logger.exception("Search failed for query '%s': %s", query, e)
        return []


async def keyword_search(
    query: str,
    user_id: str,
    limit: int = 10,
    content_type_filter: Optional[str] = None,
) -> list[dict]:
    """
    Traditional keyword-based search (backup for regex/exact matches).

    Searches in:
    - Memory title
    - Memory summary
    - Extracted text
    - Chunk text in embeddings

    Args:
        query: Search keywords
        user_id: User ID to filter results
        limit: Maximum number of results
        content_type_filter: Optional content type filter

    Returns:
        List of matching memories with match locations
    """
    if not query or not query.strip():
        return []

    try:
        # Build case-insensitive regex pattern
        keywords = [kw.strip() for kw in query.split() if kw.strip()]
        if not keywords:
            return []

        # Find memories matching any keyword
        user_memories = await PrismaMemory.prisma().find_many(
            where={"userId": user_id},
        )

        results = []
        for memory in user_memories:
            if content_type_filter and memory.type != content_type_filter:
                continue

            matched_keywords = set()
            match_locations = []
            location_weights = {"title": 1.0, "summary": 0.8, "text": 0.6}

            # Check title
            if memory.title:
                title_lower = memory.title.lower()
                title_matches = sum(1 for kw in keywords if kw.lower() in title_lower)
                if title_matches > 0:
                    for kw in keywords:
                        if kw.lower() in title_lower:
                            matched_keywords.add(kw.lower())
                    match_locations.append({
                        "chunk": memory.title,
                        "chunkIndex": 0,
                        "location": "title",
                        "matchedKeywords": title_matches,
                        "weight": location_weights["title"],
                    })

            # Check summary
            if memory.summary:
                summary_lower = memory.summary.lower()
                summary_matches = sum(1 for kw in keywords if kw.lower() in summary_lower)
                if summary_matches > 0:
                    for kw in keywords:
                        if kw.lower() in summary_lower:
                            matched_keywords.add(kw.lower())
                    match_locations.append({
                        "chunk": memory.summary[:200],
                        "chunkIndex": 0,
                        "location": "summary",
                        "matchedKeywords": summary_matches,
                        "weight": location_weights["summary"],
                    })

            # Check extracted text
            if memory.extractedText:
                text_lower = memory.extractedText.lower()
                text_matches = sum(1 for kw in keywords if kw.lower() in text_lower)
                if text_matches > 0:
                    for kw in keywords:
                        if kw.lower() in text_lower:
                            matched_keywords.add(kw.lower())
                    # Find context around first match
                    first_kw = next(kw for kw in keywords if kw.lower() in text_lower)
                    idx = text_lower.find(first_kw.lower())
                    start = max(0, idx - 50)
                    end = min(len(memory.extractedText), idx + len(first_kw) + 50)
                    context = memory.extractedText[start:end]
                    match_locations.append({
                        "chunk": context,
                        "chunkIndex": 0,
                        "location": "text",
                        "matchedKeywords": text_matches,
                        "weight": location_weights["text"],
                    })

            if match_locations:
                # Calculate accurate score based on keyword coverage and location weight
                keyword_coverage = len(matched_keywords) / len(keywords)
                best_location_weight = max(loc["weight"] for loc in match_locations)
                keyword_score = keyword_coverage * best_location_weight
                
                # Convert match_locations to final format with accurate similarity
                formatted_matches = []
                for loc in match_locations:
                    loc_score = (loc["matchedKeywords"] / len(keywords)) * loc["weight"]
                    formatted_matches.append({
                        "chunk": loc["chunk"],
                        "chunkIndex": loc["chunkIndex"],
                        "similarity": loc_score,
                    })
                
                results.append(
                    {
                        "memoryId": memory.id,
                        "title": memory.title or "Untitled",
                        "contentType": memory.type,
                        "summary": memory.summary or "",
                        "sourceUrl": memory.sourceUrl or "",
                        "matches": formatted_matches,
                        "keywordScore": keyword_score,
                        "createdAt": memory.createdAt.isoformat() if hasattr(memory.createdAt, "isoformat") else str(memory.createdAt),
                    }
                )

        logger.info("Keyword search found %d memories for: %s", len(results), query)
        return results[:limit]

    except Exception as e:
        logger.exception("Keyword search failed: %s", e)
        return []


async def hybrid_search(
    query: str,
    user_id: str,
    limit: int = 10,
    content_type_filter: Optional[str] = None,
    semantic_weight: float = 0.7,
    keyword_weight: float = 0.3,
) -> list[dict]:
    """
    Step 7: Hybrid search combining semantic and keyword matching.

    Merges results from both search methods and reranks by combined score.

    Args:
        query: Search query
        user_id: User ID
        limit: Maximum results to return
        content_type_filter: Optional content type filter
        semantic_weight: Weight for semantic search (0-1)
        keyword_weight: Weight for keyword search (0-1)

    Returns:
        Merged and ranked results
    """
    if not query or not query.strip():
        return []

    try:
        # Run both searches in parallel
        semantic_results = await search_by_content(query, user_id, limit * 2, content_type_filter)
        keyword_results = await keyword_search(query, user_id, limit * 2, content_type_filter)

        # Normalize weights
        total = semantic_weight + keyword_weight
        sem_weight = semantic_weight / total
        kw_weight = keyword_weight / total

        # Build merged results with combined scoring
        merged = {}

        # Add semantic results
        for result in semantic_results:
            mem_id = result["memoryId"]
            merged[mem_id] = {
                **result,
                "semanticScore": result.get("bestSimilarity", 0) * sem_weight,
                "keywordScore": 0,
                "combinedScore": 0,
            }

        # Add/merge keyword results
        for result in keyword_results:
            mem_id = result["memoryId"]
            keyword_score = min(1.0, len(result.get("matches", [])) / 3.0) * kw_weight

            if mem_id in merged:
                merged[mem_id]["keywordScore"] = keyword_score
                merged[mem_id]["keywordMatches"] = result.get("matches", [])
            else:
                merged[mem_id] = {
                    **result,
                    "semanticScore": 0,
                    "keywordScore": keyword_score,
                }

        # Calculate combined score
        for mem_id, result in merged.items():
            result["combinedScore"] = result.get("semanticScore", 0) + result.get("keywordScore", 0)

        # Sort by combined score
        results = sorted(merged.values(), key=lambda x: x["combinedScore"], reverse=True)

        logger.info("Hybrid search found %d memories for: %s", len(results), query)
        return results[:limit]

    except Exception as e:
        logger.exception("Hybrid search failed: %s", e)
        return []


async def get_related_memories(
    memory_id: str,
    user_id: str,
    limit: int = 5,
) -> list[dict]:
    """
    Find memories semantically similar to a given memory.

    Useful for:
    - "Related memories" sidebar
    - Browsing by concept/topic
    - Knowledge graph visualization

    Args:
        memory_id: Reference memory ID
        user_id: User ID (for permission check)
        limit: Number of related memories to return

    Returns:
        List of related memories with similarity scores
    """
    try:
        # Get the reference memory and its embeddings
        reference = await PrismaMemory.prisma().find_unique(
            where={"id": memory_id},
            include={"embeddings": True},
        )

        if not reference or reference.userId != user_id:
            return []

        if not reference.embeddings:
            logger.debug("No embeddings for reference memory %s", memory_id)
            return []

        # Get average embedding for reference (simple approach)
        embeddings_data = []
        for emb in reference.embeddings:
            try:
                vector = _deserialize_vector(emb.vector)
                if vector:
                    embeddings_data.append(vector)
            except Exception:
                pass

        if not embeddings_data:
            return []

        # Calculate average embedding
        avg_embedding = [
            sum(v[i] for v in embeddings_data) / len(embeddings_data)
            for i in range(len(embeddings_data[0]))
        ]

        # Search with this average embedding
        all_embeddings = []
        user_memories = await PrismaMemory.prisma().find_many(
            where={"userId": user_id},
            include={"embeddings": True},
        )

        for memory in user_memories:
            if memory.id == memory_id:  # Skip self
                continue

            if not memory.embeddings:
                continue

            for emb in memory.embeddings:
                try:
                    vector = _deserialize_vector(emb.vector)
                    if not vector:
                        continue

                    all_embeddings.append(
                        {
                            "id": emb.id,
                            "memoryId": emb.memoryId,
                            "embedding": vector,
                            "text": emb.chunkText,
                        }
                    )
                except Exception:
                    pass

        # Find similar embeddings
        similar = find_similar_embeddings(avg_embedding, all_embeddings, top_k=limit * 3, threshold=0.4)

        # Group by memory and take best
        results_by_memory = {}
        for match in similar:
            mem_id = match.get("id")
            if mem_id not in results_by_memory:
                # Find memory in user_memories
                for mem in user_memories:
                    if mem.id == match.get("memoryId"):
                        results_by_memory[mem_id] = {
                            "memoryId": mem.id,
                            "title": mem.title or "Untitled",
                            "similarity": match["similarity"],
                            "type": mem.type,
                        }
                        break

        results = sorted(results_by_memory.values(), key=lambda x: x["similarity"], reverse=True)
        return results[:limit]

    except Exception as e:
        logger.exception("Failed to find related memories: %s", e)
        return []
