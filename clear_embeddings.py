#!/usr/bin/env python3
"""Clear all embeddings from the database to reprocess with correct vector format."""

import asyncio
from prisma import Prisma


async def clear_embeddings():
    """Delete all embeddings from database."""
    db = Prisma()
    await db.connect()
    
    try:
        # Delete all embeddings
        result = await db.execute_raw(
            'DELETE FROM "Embedding"'
        )
        print(f'Successfully cleared embeddings from database')
    except Exception as e:
        print(f'Error clearing embeddings: {e}')
    finally:
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(clear_embeddings())
