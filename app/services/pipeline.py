"""Orchestrate extraction: PDF text, OCR, transcription, summary, tags, embeddings."""

import asyncio
import logging
from typing import Optional

from prisma.models import Embedding as PrismaEmbedding
from prisma.models import Extraction as PrismaExtraction
from prisma.models import Memory as PrismaMemory
from prisma.models import MemoryTag as PrismaMemoryTag
from prisma.models import Tag as PrismaTag
from prisma.models import Upload as PrismaUpload

from app.config import GEMINI_API_KEY, PROCESSING_ENABLED
from app.services.extraction.chunking import chunk_text, merge_small_chunks
from app.services.extraction.embedding import batch_generate_embeddings_async
from app.services.extraction.ocr import extract_text_from_image
from app.services.extraction.pdf import extract_text_from_pdf
from app.services.extraction.vision import describe_image
from app.services.extraction.webpage import extract_webpage_content
from app.services.extraction.youtube import extract_youtube_content, is_youtube_url
from app.services.extraction.summary import generate_summary as llm_summary
from app.services.extraction.tags import generate_tags as llm_tags
from app.services.extraction.transcription import transcribe_audio
from app.services.file_fetcher import fetch_file_bytes

logger = logging.getLogger(__name__)


async def run_extraction_pipeline(memory_id: str) -> None:
    """
    Load memory and its uploads; extract text (PDF/OCR/transcript);
    save Extraction rows; generate summary and tags; update Memory.
    Sets status to 'ready' on success, 'failed' on error.
    """
    if not PROCESSING_ENABLED:
        return
    try:
        memory = await PrismaMemory.prisma().find_unique(
            where={"id": memory_id},
            include={"uploads": True},
        )
        if not memory:
            logger.warning("Memory not found: %s", memory_id)
            return
        await PrismaMemory.prisma().update(
            where={"id": memory_id},
            data={"status": "processing"},
        )
        all_text_parts: list[str] = []
        if memory.sourceUrl and (memory.sourceUrl.startswith("http://") or memory.sourceUrl.startswith("https://")):
            if memory.type == "youtube" and is_youtube_url(memory.sourceUrl):
                text, _ = extract_youtube_content(memory.sourceUrl)
                if text:
                    await PrismaExtraction.prisma().create(
                        data={
                            "memoryId": memory_id,
                            "extractionType": "youtube_transcript",
                            "content": text[:500_000],
                            "confidence": None,
                        }
                    )
                    all_text_parts.append(text)
            elif memory.type == "webpage":
                text, _ = extract_webpage_content(memory.sourceUrl)
                if text:
                    await PrismaExtraction.prisma().create(
                        data={
                            "memoryId": memory_id,
                            "extractionType": "webpage",
                            "content": text[:500_000],
                            "confidence": None,
                        }
                    )
                    all_text_parts.append(text)
        # For webpage/youtube type: only process the URL, not uploads
        if memory.type not in ("webpage", "youtube"):
            for upload in memory.uploads:
                try:
                    data = await fetch_file_bytes(upload.fileUrl)
                except Exception as e:
                    logger.warning("Failed to fetch file %s: %s", upload.fileUrl[:50], e)
                    continue
                if upload.fileType == "pdf":
                    text, conf = extract_text_from_pdf(data)
                    if text:
                        await PrismaExtraction.prisma().create(
                            data={
                                "memoryId": memory_id,
                                "extractionType": "pdf_text",
                                "content": text[:500_000],
                                "confidence": conf,
                            }
                        )
                        all_text_parts.append(text)
                elif upload.fileType == "image":
                    text = ""
                    used_vision = False
                    conf: float | None = None
                    if GEMINI_API_KEY:
                        text, _ = describe_image(data, upload.fileUrl.split("/")[-1] or "image")
                        used_vision = bool(text)
                    if not text:
                        text, conf = extract_text_from_image(data)
                    if text:
                        await PrismaExtraction.prisma().create(
                            data={
                                "memoryId": memory_id,
                                "extractionType": "vision_summary" if used_vision else "ocr",
                                "content": text[:500_000],
                                "confidence": None if used_vision else conf,
                            }
                        )
                        all_text_parts.append(text)
                elif upload.fileType == "video":
                    text, _ = transcribe_audio(data, upload.fileUrl.split("/")[-1] or "audio.mp4")
                    if text:
                        await PrismaExtraction.prisma().create(
                            data={
                                "memoryId": memory_id,
                                "extractionType": "transcript",
                                "content": text[:500_000],
                                "confidence": None,
                            }
                        )
                        all_text_parts.append(text)
                elif upload.fileType == "text":
                    try:
                        text = data.decode("utf-8", errors="replace")[:500_000]
                        if text.strip():
                            await PrismaExtraction.prisma().create(
                                data={
                                    "memoryId": memory_id,
                                    "extractionType": "pdf_text",
                                    "content": text,
                                    "confidence": 1.0,
                                }
                            )
                            all_text_parts.append(text)
                    except Exception:
                        pass
        combined_text = "\n\n---\n\n".join(all_text_parts).strip()
        summary = memory.summary
        if GEMINI_API_KEY and combined_text:
            summary = llm_summary(combined_text, memory.title)
        if not summary and combined_text:
            summary = combined_text[:500] + ("..." if len(combined_text) > 500 else "")
        if not summary and memory.summary:
            summary = memory.summary
        tag_names: list[str] = []
        if GEMINI_API_KEY and combined_text:
            tag_names = llm_tags(combined_text, memory.title)
        
        # Phase 4: Generate embeddings for semantic search
        embeddings_created = 0
        if GEMINI_API_KEY and combined_text:
            try:
                # Step 2: Chunk the text
                chunks = chunk_text(combined_text, chunk_size=512, chunk_overlap=100)
                if chunks:
                    # Merge very small chunks
                    chunks = merge_small_chunks(chunks, min_size=100)
                    
                    # Step 3: Generate embeddings for each chunk
                    chunk_texts = [c["chunkText"] for c in chunks]
                    embeddings_list = await batch_generate_embeddings_async(chunk_texts)
                    
                    # Step 4: Store embeddings in database
                    for chunk, embedding in zip(chunks, embeddings_list):
                        if embedding:
                            # Ensure embedding is a list of floats
                            if isinstance(embedding, bytes):
                                # If it's bytes, try to decode as JSON
                                try:
                                    embedding = json.loads(embedding.decode('utf-8'))
                                except (json.JSONDecodeError, UnicodeDecodeError):
                                    logger.warning("Could not decode embedding bytes for chunk %d", chunk["chunkIndex"])
                                    continue
                            elif not isinstance(embedding, (list, tuple)):
                                # If it's some other object, try to convert to list
                                if hasattr(embedding, '__iter__'):
                                    embedding = list(embedding)
                                else:
                                    logger.warning("Invalid embedding type for chunk %d: %s", chunk["chunkIndex"], type(embedding))
                                    continue
                            
                            # Convert list to JSON string for storage
                            import json
                            vector_str = json.dumps(embedding)
                            
                            try:
                                await PrismaEmbedding.prisma().create(
                                    data={
                                        "memoryId": memory_id,
                                        "chunkIndex": chunk["chunkIndex"],
                                        "chunkText": chunk["chunkText"][:5000],  # Limit chunk text storage
                                        "vector": vector_str,  # Store as JSON string
                                        "modelName": "gemini-embedding-001",
                                    }
                                )
                                embeddings_created += 1
                            except Exception as e:
                                logger.warning("Failed to store embedding for chunk %d: %s", 
                                             chunk["chunkIndex"], e)
                                
                    logger.info("Created %d embeddings for memory %s", embeddings_created, memory_id)
            except Exception as e:
                logger.error("Embedding generation failed for memory %s: %s", memory_id, e)
        
        await PrismaMemory.prisma().update(
            where={"id": memory_id},
            data={
                "extractedText": combined_text[:1_000_000] if combined_text else memory.extractedText,
                "summary": summary,
                "status": "ready",
            },
        )
        for name in tag_names:
            name = name.strip().lower()[:64]
            if not name:
                continue
            tag = await PrismaTag.prisma().find_unique(where={"name": name})
            if not tag:
                tag = await PrismaTag.prisma().create(data={"name": name})
            try:
                await PrismaMemoryTag.prisma().create(
                    data={"memoryId": memory_id, "tagId": tag.id}
                )
            except Exception:
                pass  # already linked
    except Exception as e:
        logger.exception("Extraction pipeline failed for memory %s: %s", memory_id, e)
        try:
            await PrismaMemory.prisma().update(
                where={"id": memory_id},
                data={"status": "failed"},
            )
        except Exception:
            pass
