"""
Text chunking for semantic search embeddings.

Splits extracted text into meaningful chunks while preserving context.
Uses sentence boundaries and paragraph structure to maintain semantic coherence.
"""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# Configuration
DEFAULT_CHUNK_SIZE = 512  # tokens (approximate, using character count as proxy)
DEFAULT_CHUNK_OVERLAP = 100  # tokens for context preservation
SENTENCE_BOUNDARY_REGEX = r"(?<=[.!?])\s+(?=[A-Z])"
PARAGRAPH_BOUNDARY_REGEX = r"\n\n+"


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    preserve_paragraphs: bool = True,
) -> list[dict]:
    """
    Split text into meaningful chunks with overlap for context preservation.

    Args:
        text: Source text to chunk
        chunk_size: Target chunk size in characters (~4 chars per token)
        chunk_overlap: Overlap between chunks in characters
        preserve_paragraphs: Try to keep paragraphs together

    Returns:
        List of dicts with keys:
            - chunkText: The chunk content
            - chunkIndex: Position in sequence
            - startChar: Start position in original text
            - endChar: End position in original text
    """
    if not text or not text.strip():
        return []

    text = text.strip()
    chunks = []

    if preserve_paragraphs:
        # Split by paragraphs first
        paragraphs = re.split(PARAGRAPH_BOUNDARY_REGEX, text)
        paragraphs = [p.strip() for p in paragraphs if p.strip()]

        current_chunk = ""
        current_start = 0
        chunk_index = 0

        for para in paragraphs:
            # If paragraph alone is larger than chunk_size, split it further
            if len(para) > chunk_size:
                # Save current chunk if it has content
                if current_chunk.strip():
                    chunk_start = text.find(current_chunk)
                    chunks.append(
                        {
                            "chunkText": current_chunk.strip(),
                            "chunkIndex": chunk_index,
                            "startChar": chunk_start,
                            "endChar": chunk_start + len(current_chunk),
                        }
                    )
                    chunk_index += 1
                    current_chunk = ""

                # Split large paragraph by sentences
                sentences = re.split(SENTENCE_BOUNDARY_REGEX, para)
                sentences = [s.strip() for s in sentences if s.strip()]

                sent_chunk = ""
                for sent in sentences:
                    test_chunk = sent_chunk + (" " if sent_chunk else "") + sent
                    if len(test_chunk) <= chunk_size:
                        sent_chunk = test_chunk
                    else:
                        if sent_chunk:
                            chunk_start = text.find(sent_chunk)
                            chunks.append(
                                {
                                    "chunkText": sent_chunk.strip(),
                                    "chunkIndex": chunk_index,
                                    "startChar": chunk_start,
                                    "endChar": chunk_start + len(sent_chunk),
                                }
                            )
                            chunk_index += 1
                            # Overlap: include last part of previous chunk
                            sent_chunk = sent_chunk[-chunk_overlap:] + " " + sent
                        else:
                            sent_chunk = sent

                if sent_chunk.strip():
                    chunk_start = text.find(sent_chunk)
                    chunks.append(
                        {
                            "chunkText": sent_chunk.strip(),
                            "chunkIndex": chunk_index,
                            "startChar": chunk_start,
                            "endChar": chunk_start + len(sent_chunk),
                        }
                    )
                    chunk_index += 1
            else:
                # Paragraph fits in chunk
                test_chunk = current_chunk + ("\n\n" if current_chunk else "") + para
                if len(test_chunk) <= chunk_size:
                    current_chunk = test_chunk
                else:
                    if current_chunk.strip():
                        chunk_start = text.find(current_chunk)
                        chunks.append(
                            {
                                "chunkText": current_chunk.strip(),
                                "chunkIndex": chunk_index,
                                "startChar": chunk_start,
                                "endChar": chunk_start + len(current_chunk),
                            }
                        )
                        chunk_index += 1
                        # Overlap for context
                        current_chunk = current_chunk[-chunk_overlap:] + "\n\n" + para
                    else:
                        current_chunk = para

        # Add final chunk
        if current_chunk.strip():
            chunk_start = text.find(current_chunk)
            chunks.append(
                {
                    "chunkText": current_chunk.strip(),
                    "chunkIndex": chunk_index,
                    "startChar": chunk_start,
                    "endChar": chunk_start + len(current_chunk),
                }
            )

    else:
        # Simple sliding window approach
        current_pos = 0
        chunk_index = 0

        while current_pos < len(text):
            # Try to find a good break point (sentence end) near chunk_size
            chunk_end = min(current_pos + chunk_size, len(text))

            # Look for sentence boundary after chunk_size
            if chunk_end < len(text):
                # Search within next 100 chars for a sentence boundary
                search_end = min(chunk_end + 100, len(text))
                match = re.search(SENTENCE_BOUNDARY_REGEX, text[chunk_end:search_end])
                if match:
                    chunk_end = chunk_end + match.start() + len(match.group(0))

            chunk_text = text[current_pos:chunk_end].strip()
            if chunk_text:
                chunks.append(
                    {
                        "chunkText": chunk_text,
                        "chunkIndex": chunk_index,
                        "startChar": current_pos,
                        "endChar": chunk_end,
                    }
                )
                chunk_index += 1

            # Move to next chunk with overlap
            current_pos = chunk_end - chunk_overlap
            if current_pos >= chunk_end:
                break

    logger.info(
        "Chunked text into %d chunks (size ~%d, overlap ~%d)",
        len(chunks),
        chunk_size,
        chunk_overlap,
    )
    return chunks


def merge_small_chunks(chunks: list[dict], min_size: int = 100) -> list[dict]:
    """
    Merge chunks that are smaller than min_size with adjacent chunks.

    Args:
        chunks: List of chunk dicts
        min_size: Minimum chunk size in characters

    Returns:
        List of merged chunks with updated indices
    """
    if not chunks:
        return []

    merged = []
    i = 0

    while i < len(chunks):
        chunk = chunks[i]

        # If chunk is small, try to merge with next
        if len(chunk["chunkText"]) < min_size and i < len(chunks) - 1:
            next_chunk = chunks[i + 1]
            merged_text = chunk["chunkText"] + " " + next_chunk["chunkText"]

            merged_chunk = {
                "chunkText": merged_text,
                "chunkIndex": len(merged),
                "startChar": chunk["startChar"],
                "endChar": next_chunk["endChar"],
            }
            merged.append(merged_chunk)
            i += 2
        else:
            chunk["chunkIndex"] = len(merged)
            merged.append(chunk)
            i += 1

    return merged
