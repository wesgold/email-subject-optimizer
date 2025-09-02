"""Check database structure and contents."""

import asyncio
from sqlalchemy import text
from src.config.database import AsyncSessionLocal

async def main():
    async with AsyncSessionLocal() as session:
        # Check ABTest table structure
        result = await session.execute(text("SELECT sql FROM sqlite_master WHERE type='table' AND name='ab_tests'"))
        schema = result.scalar()
        print("ABTest table schema:")
        print(schema)
        print()
        
        # Get recent tests
        result = await session.execute(text("SELECT id, email_content_hash, name, status FROM ab_tests ORDER BY created_at DESC LIMIT 3"))
        tests = result.fetchall()
        print("Recent tests:")
        for test in tests:
            print(f"  ID: {test[0]}")
            print(f"  Hash: {test[1]}")
            print(f"  Name: {test[2]}")
            print(f"  Status: {test[3]}")
            print()
        
        # Check if we have UUID variations
        result = await session.execute(text("SELECT id, ab_test_id, subject_line FROM ab_test_variations LIMIT 3"))
        variations = result.fetchall()
        print("Sample variations:")
        for var in variations:
            print(f"  ID: {var[0]}")
            print(f"  Test ID: {var[1]}")
            print(f"  Subject: {var[2]}")
            print()

if __name__ == "__main__":
    asyncio.run(main())