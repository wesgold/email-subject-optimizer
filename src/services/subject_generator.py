import asyncio
import os
import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from dotenv import load_dotenv

from src.config.cache import cache_manager
from src.config.database import AsyncSessionLocal
from src.models.ab_testing import ABTest, TestVariation
from src.services.ai_providers import OpenAIProvider, RateLimitConfig

load_dotenv()

class SubjectGeneratorService:
    def __init__(self):
        self.rate_limit_config = RateLimitConfig()
        self.ai_provider = self._initialize_ai_provider()
    
    def _initialize_ai_provider(self):
        openai_key = os.getenv("OPENAI_API_KEY")
        
        if openai_key:
            return OpenAIProvider(openai_key, self.rate_limit_config)
        else:
            raise ValueError("No OpenAI API key configured. Set OPENAI_API_KEY in your .env file")
    
    async def generate_subject_variations(
        self, 
        email_content: str, 
        original_subject: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate 5 subject line variations with caching and A/B test tracking
        """
        # Check cache first
        cache_key = email_content
        cached_result = await cache_manager.get(cache_key)
        
        if cached_result:
            return {
                "ab_test_id": cached_result["ab_test_id"],
                "variations": cached_result["variations"],
                "cached": True
            }
        
        # Generate new variations
        subject_lines = await self.ai_provider.generate_subject_lines(email_content, original_subject)
        
        # Create A/B test record
        async with AsyncSessionLocal() as session:
            ab_test = ABTest(
                id=cache_manager._generate_cache_key(email_content),
                email_content_hash=cache_manager._generate_cache_key(email_content),
                original_subject=original_subject
            )
            session.add(ab_test)
            
            # Create variations
            variations = []
            variation_objects = []
            for i, subject_line in enumerate(subject_lines):
                variation = TestVariation(
                    id=str(uuid.uuid4()),
                    ab_test_id=ab_test.id,
                    subject_line=subject_line,
                    variation_index=i
                )
                session.add(variation)
                variation_objects.append(variation)
            
            await session.commit()
            
            # Build response after commit to get IDs
            for variation in variation_objects:
                variations.append({
                    "id": str(variation.id),
                    "subject_line": variation.subject_line,
                    "variation_index": variation.variation_index
                })
        
        # Cache the result
        result = {
            "ab_test_id": ab_test.id,
            "variations": variations,
            "cached": False
        }
        
        await cache_manager.set(cache_key, {
            "ab_test_id": ab_test.id,
            "variations": variations
        }, ttl=3600)
        
        return result