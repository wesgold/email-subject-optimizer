"""Recreate database with new schema."""

import asyncio
from sqlalchemy import text
from src.config.database import engine, create_tables, AsyncSessionLocal
from src.models.ab_testing import Base

async def main():
    async with engine.begin() as conn:
        # Drop all existing tables
        print("Dropping existing tables...")
        await conn.execute(text("DROP TABLE IF EXISTS email_events"))
        await conn.execute(text("DROP TABLE IF EXISTS test_variations"))
        await conn.execute(text("DROP TABLE IF EXISTS ab_test_events"))
        await conn.execute(text("DROP TABLE IF EXISTS ab_test_variations"))
        await conn.execute(text("DROP TABLE IF EXISTS ab_tests"))
        
        # Create new tables
        print("Creating new tables...")
        await conn.run_sync(Base.metadata.create_all)
        
    print("Database recreated successfully!")
    
    # Verify the schema
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("SELECT sql FROM sqlite_master WHERE type='table' AND name='ab_tests'"))
        schema = result.scalar()
        print("\nNew ABTest table schema:")
        print(schema)

if __name__ == "__main__":
    asyncio.run(main())