import asyncio
import os
import sys
from pathlib import Path

# Add the parent directory to sys.path to import app
sys.path.append(str(Path(__file__).parent.parent))

from prisma import Prisma
from app.services.extraction.category import generate_category

async def backfill():
    db = Prisma()
    await db.connect()
    
    # Get all memories with no category
    memories = await db.memory.find_many(
        where={
            "OR": [
                {"category": None},
                {"category": ""}
            ]
        }
    )
    
    print(f"Found {len(memories)} memories to categorize...")
    
    for memory in memories:
        print(f"Categorizing memory: {memory.title} ({memory.id})")
        
        # Combine title and summary for better categorization
        content = f"Title: {memory.title or 'Untitled'}\nSummary: {memory.summary or ''}\nText: {(memory.extractedText or '')[:500]}"
        
        try:
            category = generate_category(content)
            print(f"  -> Category: {category}")
            
            await db.memory.update(
                where={"id": memory.id},
                data={"category": category}
            )
        except Exception as e:
            print(f"  !! Error categorizing memory {memory.id}: {e}")
            
    await db.disconnect()
    print("Backfill complete.")

if __name__ == "__main__":
    asyncio.run(backfill())
