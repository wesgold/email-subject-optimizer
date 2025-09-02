"""Direct test of UUID creation."""

import asyncio
import uuid
from src.config.database import AsyncSessionLocal
from src.models.ab_testing import ABTest
from sqlalchemy import text

async def main():
    async with AsyncSessionLocal() as session:
        # Create a test with UUID
        test_id = uuid.uuid4()
        print(f"Creating test with UUID: {test_id}")
        
        test = ABTest(
            id=test_id,
            email_content_hash="test_hash_12345",
            original_subject="Test Subject",
            name="Test Name",
            status="active"
        )
        
        print(f"ABTest object id: {test.id}")
        print(f"ABTest object type: {type(test.id)}")
        
        session.add(test)
        await session.commit()
        
        print(f"Test created successfully with ID: {test.id}")
        
        # Query it back
        result = await session.execute(text("SELECT id, name FROM ab_tests WHERE email_content_hash = 'test_hash_12345'"))
        row = result.fetchone()
        if row:
            print(f"Retrieved test ID from DB: {row[0]}")
            print(f"Retrieved test name from DB: {row[1]}")

if __name__ == "__main__":
    asyncio.run(main())