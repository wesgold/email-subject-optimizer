"""Test script for Phase 4 functionality."""

import asyncio
from src.config.database import async_session
from sqlalchemy import text

async def main():
    async with async_session() as session:
        # Get test IDs
        result = await session.execute(text('SELECT id, email_content_hash FROM ab_tests LIMIT 5'))
        tests = result.fetchall()
        print("Tests in database:")
        for test in tests:
            print(f"  ID: {test[0]}")
            print(f"  Hash: {test[1]}")
            print()

if __name__ == "__main__":
    asyncio.run(main())