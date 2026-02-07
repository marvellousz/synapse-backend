#!/usr/bin/env python3
import asyncio
from prisma import Prisma

async def check_embeddings():
    db = Prisma()
    await db.connect()
    
    # Check count using query_raw
    result = await db.query_raw('SELECT COUNT(*) as count FROM "Embedding"')
    print(f'Total embeddings: {result[0]["count"] if result else 0}')
    
    # Check if any memories exist
    memories_count = await db.query_raw('SELECT COUNT(*) as count FROM "Memory"')
    print(f'Total memories: {memories_count[0]["count"] if memories_count else 0}')
    
    # List all memories with details
    all_memories = await db.query_raw(
        'SELECT id, title, type, status, "userId" FROM "Memory"'
    )
    print(f'\nMemory details:')
    for mem in all_memories:
        print(f'  - ID: {mem["id"][:8]}... Title: {mem["title"]} Type: {mem["type"]} Status: {mem["status"]}')
    
    # Check embeddings per memory
    embeddings = await db.query_raw(
        'SELECT "memoryId", COUNT(*) as count FROM "Embedding" GROUP BY "memoryId"'
    )
    print(f'\nEmbeddings per memory:')
    for emb in embeddings:
        print(f'  - Memory {emb["memoryId"][:8]}...: {emb["count"]} embeddings')
    
    await db.disconnect()

asyncio.run(check_embeddings())
