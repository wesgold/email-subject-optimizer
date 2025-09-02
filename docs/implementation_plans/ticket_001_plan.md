# AI Email Subject Line Optimizer - Initial Setup Implementation Plan

## Overview

This plan implements a production-ready AI Email Subject Line Optimizer with FastAPI, Redis caching, SQLAlchemy 2.0 with AsyncPG, and multi-armed bandit A/B testing. The system generates 5 subject line variations (≤60 chars) using AI with caching based on SHA256 hashes of email content, implementing exponential backoff with jitter for rate limiting.

## Current State Analysis

The project is in initial setup phase:
- Empty `src/` and `tests/` directories 
- `requirements.txt` contains all necessary dependencies (FastAPI, OpenAI, Anthropic, Redis, SQLAlchemy 2.0, etc.)
- Basic project structure with `docs/`, `config/`, and `data/` directories
- No database schema or API endpoints implemented yet

### Key Discoveries:
- Dependencies already defined in `requirements.txt` align with research findings
- Project structure follows Python best practices with separate `src/` and `tests/` directories
- Environment configuration ready via `.env` file
- No existing implementation to conflict with new development

## Desired End State

A fully functional AI Email Subject Line Optimizer that:
- Accepts email content via REST API and returns 5 optimized subject line variations
- Uses SHA256 hashing for efficient caching with Redis backend
- Implements multi-armed bandit algorithm for A/B testing with 95% confidence levels
- Tracks email events (opens, clicks) for performance analytics
- Handles rate limiting with exponential backoff and jitter
- Supports both OpenAI and Anthropic AI providers
- Maintains async architecture throughout with connection pooling (20-30 connections)

## What We're NOT Doing

- Email sending functionality (this is subject line generation only)
- User authentication/authorization (assuming internal tool usage)
- Multi-tenancy support
- Real-time notifications or webhooks
- Advanced ML model training (using existing LLM APIs)
- Email template management
- GDPR compliance features (for future iteration)

## Implementation Approach

Following async-first architecture with three core layers:
1. **API Layer**: FastAPI with async endpoints
2. **Service Layer**: Business logic with caching and AI integration
3. **Data Layer**: SQLAlchemy 2.0 with AsyncPG for PostgreSQL/SQLite

Using SHA256 content hashing for cache keys, temperature 0.85 for AI generation, and multi-armed bandit algorithm for optimal A/B test selection.

## Phase 1: Core Infrastructure & Database Setup

### Overview
Establish the foundational infrastructure including database schema, connection management, and basic project structure.

### Changes Required:

#### 1. Database Models & Schema
**File**: `src/models/__init__.py`
**Changes**: Create database models for A/B testing system

```python
# Empty __init__.py for models package
```

**File**: `src/models/ab_testing.py`
**Changes**: Define SQLAlchemy 2.0 models with async support

```python
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, Float, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid

class Base(DeclarativeBase):
    pass

class ABTest(Base):
    __tablename__ = "ab_tests"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # SHA256 hash
    email_content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    original_subject: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Relationship to variations
    variations = relationship("TestVariation", back_populates="ab_test")

class TestVariation(Base):
    __tablename__ = "test_variations"
    
    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ab_test_id: Mapped[str] = mapped_column(String(64), ForeignKey("ab_tests.id"))
    subject_line: Mapped[str] = mapped_column(String(255), nullable=False)
    variation_index: Mapped[int] = mapped_column(Integer, nullable=False)  # 0-4
    
    # Multi-armed bandit metrics
    times_selected: Mapped[int] = mapped_column(Integer, default=0)
    times_sent: Mapped[int] = mapped_column(Integer, default=0)
    opens: Mapped[int] = mapped_column(Integer, default=0)
    clicks: Mapped[int] = mapped_column(Integer, default=0)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationship back to test
    ab_test = relationship("ABTest", back_populates="variations")

class EmailEvent(Base):
    __tablename__ = "email_events"
    
    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    variation_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("test_variations.id"))
    event_type: Mapped[str] = mapped_column(String(20), nullable=False)  # 'sent', 'opened', 'clicked'
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
```

#### 2. Database Configuration
**File**: `src/config/database.py`
**Changes**: Setup async SQLAlchemy with connection pooling

```python
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import QueuePool
from src.models.ab_testing import Base

DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "sqlite+aiosqlite:///./data/email_optimizer.db"
)

# Connection pooling configuration (20-30 connections)
engine = create_async_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
    echo=False
)

AsyncSessionLocal = async_sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
```

#### 3. Cache Configuration
**File**: `src/config/cache.py`
**Changes**: Setup Redis with fallback to DiskCache

```python
import os
import redis.asyncio as redis
from diskcache import Cache
from typing import Optional, Union
import json
import hashlib

class CacheManager:
    def __init__(self):
        self.redis_url = os.getenv("REDIS_URL")
        self.redis_client: Optional[redis.Redis] = None
        self.disk_cache = Cache('./data/cache')
        
    async def initialize(self):
        if self.redis_url:
            try:
                self.redis_client = redis.from_url(
                    self.redis_url,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5
                )
                await self.redis_client.ping()
                print("Redis connected successfully")
            except Exception as e:
                print(f"Redis connection failed, falling back to disk cache: {e}")
                self.redis_client = None
    
    def _generate_cache_key(self, content: str) -> str:
        """Generate SHA256 hash for cache key"""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    async def get(self, key: str) -> Optional[dict]:
        cache_key = self._generate_cache_key(key)
        
        if self.redis_client:
            try:
                result = await self.redis_client.get(cache_key)
                return json.loads(result) if result else None
            except Exception:
                pass  # Fall back to disk cache
        
        # Disk cache fallback
        return self.disk_cache.get(cache_key)
    
    async def set(self, key: str, value: dict, ttl: int = 3600):
        cache_key = self._generate_cache_key(key)
        
        if self.redis_client:
            try:
                await self.redis_client.setex(cache_key, ttl, json.dumps(value))
                return
            except Exception:
                pass  # Fall back to disk cache
        
        # Disk cache fallback
        self.disk_cache.set(cache_key, value, expire=ttl)

# Global cache instance
cache_manager = CacheManager()
```

### Success Criteria:

#### Automated Verification:
- [ ] Database models import without errors: `python -c "from src.models.ab_testing import ABTest, TestVariation, EmailEvent"`
- [ ] Database tables can be created: `python -c "import asyncio; from src.config.database import create_tables; asyncio.run(create_tables())"`
- [ ] Cache manager initializes: `python -c "import asyncio; from src.config.cache import cache_manager; asyncio.run(cache_manager.initialize())"`
- [ ] SHA256 hashing works: `python -c "from src.config.cache import CacheManager; print(len(CacheManager()._generate_cache_key('test'))) == 64"`

#### Manual Verification:
- [ ] Database file is created in `data/` directory when using SQLite
- [ ] Redis connection works if Redis URL is provided
- [ ] Disk cache falls back properly when Redis is unavailable
- [ ] Database schema matches the three-table design from research

---

## Phase 2: AI Integration & Rate Limiting

### Overview
Implement AI service integration with both OpenAI and Anthropic, including exponential backoff with jitter for rate limiting and subject line generation logic.

### Changes Required:

#### 1. AI Service Abstraction
**File**: `src/services/__init__.py`
**Changes**: Create services package

```python
# Empty __init__.py for services package
```

**File**: `src/services/ai_providers.py`
**Changes**: Abstract AI provider interface with rate limiting

```python
import asyncio
import random
import time
from abc import ABC, abstractmethod
from typing import List, Optional
import openai
import anthropic
import httpx
from dataclasses import dataclass

@dataclass
class RateLimitConfig:
    initial_delay: float = 1.0
    max_delay: float = 60.0
    multiplier: float = 2.0
    jitter: bool = True
    max_retries: int = 5

class AIProvider(ABC):
    def __init__(self, api_key: str, rate_limit_config: RateLimitConfig):
        self.api_key = api_key
        self.rate_limit_config = rate_limit_config
    
    @abstractmethod
    async def generate_subject_lines(self, email_content: str, original_subject: Optional[str] = None) -> List[str]:
        pass
    
    async def _exponential_backoff_retry(self, func, *args, **kwargs):
        """Implement exponential backoff with jitter"""
        delay = self.rate_limit_config.initial_delay
        
        for attempt in range(self.rate_limit_config.max_retries):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                if attempt == self.rate_limit_config.max_retries - 1:
                    raise e
                
                # Add jitter to prevent thundering herd
                if self.rate_limit_config.jitter:
                    jitter_delay = delay * (0.5 + random.random() * 0.5)
                else:
                    jitter_delay = delay
                
                await asyncio.sleep(jitter_delay)
                delay = min(delay * self.rate_limit_config.multiplier, self.rate_limit_config.max_delay)

class OpenAIProvider(AIProvider):
    def __init__(self, api_key: str, rate_limit_config: RateLimitConfig):
        super().__init__(api_key, rate_limit_config)
        self.client = openai.AsyncOpenAI(
            api_key=api_key,
            http_client=httpx.AsyncClient(timeout=30.0)
        )
    
    async def _generate_subject_lines_impl(self, email_content: str, original_subject: Optional[str] = None) -> List[str]:
        prompt = self._build_prompt(email_content, original_subject)
        
        response = await self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are an expert email marketer specializing in subject line optimization."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.85,
            max_tokens=300
        )
        
        content = response.choices[0].message.content
        return self._parse_subject_lines(content)
    
    async def generate_subject_lines(self, email_content: str, original_subject: Optional[str] = None) -> List[str]:
        return await self._exponential_backoff_retry(
            self._generate_subject_lines_impl, 
            email_content, 
            original_subject
        )
    
    def _build_prompt(self, email_content: str, original_subject: Optional[str] = None) -> str:
        base_prompt = f"""
Generate exactly 5 compelling email subject lines for the following email content. Each subject line must be 60 characters or less.

Email Content:
{email_content[:1000]}

Requirements:
- Maximum 60 characters per subject line
- Focus on urgency, curiosity, or value proposition
- Avoid spam trigger words
- Make them action-oriented
- Ensure variety in approach (different psychological triggers)

Original subject: {original_subject if original_subject else 'None provided'}

Format your response as a numbered list:
1. [Subject line 1]
2. [Subject line 2]
3. [Subject line 3]
4. [Subject line 4]
5. [Subject line 5]
"""
        return base_prompt
    
    def _parse_subject_lines(self, content: str) -> List[str]:
        lines = []
        for line in content.strip().split('\n'):
            if line.strip() and any(line.startswith(f"{i}.") for i in range(1, 6)):
                subject = line.split('.', 1)[1].strip()
                # Remove quotes if present
                subject = subject.strip('"').strip("'")
                if len(subject) <= 60:
                    lines.append(subject)
        
        # Ensure we have exactly 5 lines
        while len(lines) < 5:
            lines.append(f"Optimized Subject {len(lines) + 1}")
        
        return lines[:5]

class AnthropicProvider(AIProvider):
    def __init__(self, api_key: str, rate_limit_config: RateLimitConfig):
        super().__init__(api_key, rate_limit_config)
        self.client = anthropic.AsyncAnthropic(
            api_key=api_key,
            timeout=30.0
        )
    
    async def _generate_subject_lines_impl(self, email_content: str, original_subject: Optional[str] = None) -> List[str]:
        prompt = self._build_prompt(email_content, original_subject)
        
        response = await self.client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=300,
            temperature=0.85,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        return self._parse_subject_lines(response.content[0].text)
    
    async def generate_subject_lines(self, email_content: str, original_subject: Optional[str] = None) -> List[str]:
        return await self._exponential_backoff_retry(
            self._generate_subject_lines_impl, 
            email_content, 
            original_subject
        )
    
    def _build_prompt(self, email_content: str, original_subject: Optional[str] = None) -> str:
        # Same prompt building logic as OpenAI
        return OpenAIProvider(self.api_key, self.rate_limit_config)._build_prompt(email_content, original_subject)
    
    def _parse_subject_lines(self, content: str) -> List[str]:
        # Same parsing logic as OpenAI
        return OpenAIProvider(self.api_key, self.rate_limit_config)._parse_subject_lines(content)
```

#### 2. Subject Line Service
**File**: `src/services/subject_generator.py`
**Changes**: Main service orchestrating AI generation, caching, and A/B testing

```python
import asyncio
import os
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.config.cache import cache_manager
from src.config.database import AsyncSessionLocal
from src.models.ab_testing import ABTest, TestVariation
from src.services.ai_providers import OpenAIProvider, AnthropicProvider, RateLimitConfig

class SubjectGeneratorService:
    def __init__(self):
        self.rate_limit_config = RateLimitConfig()
        self.ai_provider = self._initialize_ai_provider()
    
    def _initialize_ai_provider(self):
        openai_key = os.getenv("OPENAI_API_KEY")
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        
        if openai_key:
            return OpenAIProvider(openai_key, self.rate_limit_config)
        elif anthropic_key:
            return AnthropicProvider(anthropic_key, self.rate_limit_config)
        else:
            raise ValueError("No AI API key configured. Set OPENAI_API_KEY or ANTHROPIC_API_KEY")
    
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
            for i, subject_line in enumerate(subject_lines):
                variation = TestVariation(
                    ab_test_id=ab_test.id,
                    subject_line=subject_line,
                    variation_index=i
                )
                session.add(variation)
                variations.append({
                    "id": str(variation.id),
                    "subject_line": subject_line,
                    "variation_index": i
                })
            
            await session.commit()
        
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
```

### Success Criteria:

#### Automated Verification:
- [ ] AI providers can be imported: `python -c "from src.services.ai_providers import OpenAIProvider, AnthropicProvider"`
- [ ] Rate limiting config works: `python -c "from src.services.ai_providers import RateLimitConfig; print(RateLimitConfig().max_retries)"`
- [ ] Subject generator service initializes: `python -c "from src.services.subject_generator import SubjectGeneratorService"`
- [ ] Environment variables are properly read: `python -c "import os; print('AI key configured:', bool(os.getenv('OPENAI_API_KEY') or os.getenv('ANTHROPIC_API_KEY')))"`

#### Manual Verification:
- [ ] Subject line generation produces exactly 5 variations ≤60 characters each
- [ ] Rate limiting activates under API stress conditions
- [ ] Cache hit/miss behavior works correctly
- [ ] Both OpenAI and Anthropic providers generate quality subject lines
- [ ] A/B test records are created in database with proper relationships

---

## Phase 3: Multi-Armed Bandit A/B Testing

### Overview
Implement the multi-armed bandit algorithm for optimal subject line selection and event tracking for performance analytics.

### Changes Required:

#### 1. Multi-Armed Bandit Algorithm
**File**: `src/services/ab_testing.py`
**Changes**: Implement multi-armed bandit with Thompson sampling

```python
import math
import random
from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from src.models.ab_testing import ABTest, TestVariation, EmailEvent

class MultiArmedBanditService:
    def __init__(self, confidence_level: float = 0.95, min_samples: int = 5000):
        self.confidence_level = confidence_level
        self.min_samples = min_samples
    
    async def select_best_variation(self, ab_test_id: str, session: AsyncSession) -> Optional[TestVariation]:
        """
        Select the best performing variation using Thompson sampling
        """
        # Get all variations for this test
        result = await session.execute(
            select(TestVariation).where(TestVariation.ab_test_id == ab_test_id)
        )
        variations = result.scalars().all()
        
        if not variations:
            return None
        
        # If insufficient data, use round-robin exploration
        total_samples = sum(v.times_sent for v in variations)
        if total_samples < self.min_samples:
            return self._round_robin_selection(variations)
        
        # Thompson sampling for exploitation
        return self._thompson_sampling(variations)
    
    def _round_robin_selection(self, variations: List[TestVariation]) -> TestVariation:
        """Round-robin selection for exploration phase"""
        return min(variations, key=lambda v: v.times_selected)
    
    def _thompson_sampling(self, variations: List[TestVariation]) -> TestVariation:
        """Thompson sampling based on click-through rates"""
        sampled_rates = []
        
        for variation in variations:
            # Beta distribution parameters
            clicks = variation.clicks
            impressions = variation.times_sent
            
            if impressions == 0:
                sampled_rates.append(0.0)
                continue
            
            # Beta(α, β) where α = clicks + 1, β = impressions - clicks + 1
            alpha = clicks + 1
            beta = impressions - clicks + 1
            
            # Sample from Beta distribution
            sampled_rate = random.betavariate(alpha, beta)
            sampled_rates.append(sampled_rate)
        
        # Select variation with highest sampled rate
        best_idx = sampled_rates.index(max(sampled_rates))
        return variations[best_idx]
    
    async def calculate_confidence_intervals(self, ab_test_id: str, session: AsyncSession) -> Dict[str, Dict[str, float]]:
        """
        Calculate confidence intervals for all variations
        """
        result = await session.execute(
            select(TestVariation).where(TestVariation.ab_test_id == ab_test_id)
        )
        variations = result.scalars().all()
        
        confidence_intervals = {}
        
        for variation in variations:
            if variation.times_sent == 0:
                confidence_intervals[str(variation.id)] = {
                    "lower": 0.0,
                    "upper": 0.0,
                    "click_rate": 0.0
                }
                continue
            
            click_rate = variation.clicks / variation.times_sent
            n = variation.times_sent
            
            # Wilson score confidence interval
            z = 1.96  # 95% confidence
            denominator = 1 + z**2 / n
            centre_adjusted_probability = click_rate + z*z / (2*n)
            adjusted_standard_deviation = math.sqrt((click_rate * (1 - click_rate) + z*z / (4*n)) / n)
            
            lower = (centre_adjusted_probability - z * adjusted_standard_deviation) / denominator
            upper = (centre_adjusted_probability + z * adjusted_standard_deviation) / denominator
            
            confidence_intervals[str(variation.id)] = {
                "lower": max(0.0, lower),
                "upper": min(1.0, upper),
                "click_rate": click_rate
            }
        
        return confidence_intervals
    
    async def record_event(
        self, 
        variation_id: str, 
        event_type: str, 
        session: AsyncSession,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None
    ):
        """
        Record email events and update variation statistics
        """
        # Record the event
        event = EmailEvent(
            variation_id=variation_id,
            event_type=event_type,
            user_agent=user_agent,
            ip_address=ip_address
        )
        session.add(event)
        
        # Update variation statistics
        if event_type == "sent":
            await session.execute(
                update(TestVariation)
                .where(TestVariation.id == variation_id)
                .values(times_sent=TestVariation.times_sent + 1)
            )
        elif event_type == "opened":
            await session.execute(
                update(TestVariation)
                .where(TestVariation.id == variation_id)
                .values(opens=TestVariation.opens + 1)
            )
        elif event_type == "clicked":
            await session.execute(
                update(TestVariation)
                .where(TestVariation.id == variation_id)
                .values(clicks=TestVariation.clicks + 1)
            )
        
        await session.commit()
```

#### 2. Analytics Service
**File**: `src/services/analytics.py`
**Changes**: Service for generating A/B test analytics and reports

```python
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from src.models.ab_testing import ABTest, TestVariation, EmailEvent

class AnalyticsService:
    def __init__(self):
        pass
    
    async def get_test_performance(self, ab_test_id: str, session: AsyncSession) -> Dict[str, Any]:
        """Get performance metrics for an A/B test"""
        # Get test info
        test_result = await session.execute(
            select(ABTest).where(ABTest.id == ab_test_id)
        )
        test = test_result.scalar_one_or_none()
        
        if not test:
            return {"error": "Test not found"}
        
        # Get variations with metrics
        variations_result = await session.execute(
            select(TestVariation).where(TestVariation.ab_test_id == ab_test_id)
        )
        variations = variations_result.scalars().all()
        
        performance_data = {
            "test_id": ab_test_id,
            "created_at": test.created_at.isoformat(),
            "original_subject": test.original_subject,
            "is_active": test.is_active,
            "variations": []
        }
        
        total_sent = sum(v.times_sent for v in variations)
        
        for variation in variations:
            open_rate = (variation.opens / variation.times_sent) if variation.times_sent > 0 else 0
            click_rate = (variation.clicks / variation.times_sent) if variation.times_sent > 0 else 0
            
            performance_data["variations"].append({
                "id": str(variation.id),
                "subject_line": variation.subject_line,
                "variation_index": variation.variation_index,
                "times_sent": variation.times_sent,
                "opens": variation.opens,
                "clicks": variation.clicks,
                "open_rate": round(open_rate * 100, 2),
                "click_rate": round(click_rate * 100, 2),
                "selection_percentage": round((variation.times_selected / max(1, total_sent)) * 100, 2)
            })
        
        return performance_data
    
    async def get_top_performing_subjects(
        self, 
        session: AsyncSession, 
        limit: int = 10,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """Get top performing subject lines from last N days"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        result = await session.execute(
            select(TestVariation, ABTest)
            .join(ABTest, TestVariation.ab_test_id == ABTest.id)
            .where(ABTest.created_at >= cutoff_date)
            .where(TestVariation.times_sent > 100)  # Minimum sample size
            .order_by((TestVariation.clicks / TestVariation.times_sent).desc())
            .limit(limit)
        )
        
        top_subjects = []
        for variation, test in result:
            click_rate = (variation.clicks / variation.times_sent) if variation.times_sent > 0 else 0
            open_rate = (variation.opens / variation.times_sent) if variation.times_sent > 0 else 0
            
            top_subjects.append({
                "subject_line": variation.subject_line,
                "click_rate": round(click_rate * 100, 2),
                "open_rate": round(open_rate * 100, 2),
                "times_sent": variation.times_sent,
                "test_created": test.created_at.isoformat()
            })
        
        return top_subjects
    
    async def get_dashboard_metrics(self, session: AsyncSession) -> Dict[str, Any]:
        """Get key metrics for analytics dashboard"""
        # Total tests
        total_tests = await session.execute(select(func.count(ABTest.id)))
        total_tests_count = total_tests.scalar()
        
        # Active tests
        active_tests = await session.execute(
            select(func.count(ABTest.id)).where(ABTest.is_active == True)
        )
        active_tests_count = active_tests.scalar()
        
        # Total emails sent
        total_sent = await session.execute(select(func.sum(TestVariation.times_sent)))
        total_sent_count = total_sent.scalar() or 0
        
        # Overall click rate
        total_clicks = await session.execute(select(func.sum(TestVariation.clicks)))
        total_clicks_count = total_clicks.scalar() or 0
        
        overall_click_rate = (total_clicks_count / total_sent_count * 100) if total_sent_count > 0 else 0
        
        # Tests created this week
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_tests = await session.execute(
            select(func.count(ABTest.id)).where(ABTest.created_at >= week_ago)
        )
        recent_tests_count = recent_tests.scalar()
        
        return {
            "total_tests": total_tests_count,
            "active_tests": active_tests_count,
            "total_emails_sent": total_sent_count,
            "overall_click_rate": round(overall_click_rate, 2),
            "tests_created_this_week": recent_tests_count
        }
```

### Success Criteria:

#### Automated Verification:
- [ ] Multi-armed bandit service imports: `python -c "from src.services.ab_testing import MultiArmedBanditService"`
- [ ] Analytics service imports: `python -c "from src.services.analytics import AnalyticsService"`
- [ ] Thompson sampling math works: `python -c "from src.services.ab_testing import MultiArmedBanditService; print('Service initialized')"`
- [ ] Confidence interval calculation executes: `python -c "import math; print('Wilson score test:', math.sqrt(0.5 * 0.5 / 100))"`

#### Manual Verification:
- [ ] Multi-armed bandit selects variations with insufficient data using round-robin
- [ ] Thompson sampling favors high-performing variations with sufficient data
- [ ] Confidence intervals are calculated correctly using Wilson score method
- [ ] Event tracking updates variation statistics properly
- [ ] Analytics provide meaningful insights about test performance

---

## Phase 4: FastAPI REST API Implementation

### Overview
Create the REST API endpoints for subject line generation, event tracking, and analytics using FastAPI with async patterns.

### Changes Required:

#### 1. API Models (Pydantic)
**File**: `src/api/__init__.py`
**Changes**: Create API package

```python
# Empty __init__.py for API package
```

**File**: `src/api/models.py`
**Changes**: Define Pydantic models for API requests/responses

```python
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator
from datetime import datetime

class SubjectGenerationRequest(BaseModel):
    email_content: str = Field(..., min_length=10, max_length=10000, description="The email content to generate subjects for")
    original_subject: Optional[str] = Field(None, max_length=255, description="Optional original subject line")
    
    @validator('email_content')
    def validate_email_content(cls, v):
        if not v.strip():
            raise ValueError('Email content cannot be empty')
        return v.strip()

class SubjectVariation(BaseModel):
    id: str
    subject_line: str = Field(..., max_length=60)
    variation_index: int
    
class SubjectGenerationResponse(BaseModel):
    ab_test_id: str
    variations: List[SubjectVariation]
    cached: bool = False
    generated_at: datetime = Field(default_factory=datetime.utcnow)

class EventTrackingRequest(BaseModel):
    variation_id: str
    event_type: str = Field(..., regex="^(sent|opened|clicked)$")
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None

class EventTrackingResponse(BaseModel):
    success: bool
    message: str

class TestPerformanceResponse(BaseModel):
    test_id: str
    created_at: str
    original_subject: Optional[str]
    is_active: bool
    variations: List[Dict[str, Any]]

class TopPerformingSubject(BaseModel):
    subject_line: str
    click_rate: float
    open_rate: float
    times_sent: int
    test_created: str

class DashboardMetrics(BaseModel):
    total_tests: int
    active_tests: int
    total_emails_sent: int
    overall_click_rate: float
    tests_created_this_week: int

class HealthCheckResponse(BaseModel):
    status: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    database: str
    cache: str
```

#### 2. Main FastAPI Application
**File**: `src/main.py`
**Changes**: Main application with all endpoints

```python
import os
from contextlib import asynccontextmanager
from typing import List
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.database import get_db, create_tables
from src.config.cache import cache_manager
from src.services.subject_generator import SubjectGeneratorService
from src.services.ab_testing import MultiArmedBanditService
from src.services.analytics import AnalyticsService
from src.api.models import (
    SubjectGenerationRequest, SubjectGenerationResponse,
    EventTrackingRequest, EventTrackingResponse,
    TestPerformanceResponse, TopPerformingSubject,
    DashboardMetrics, HealthCheckResponse
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown"""
    # Startup
    await cache_manager.initialize()
    await create_tables()
    yield
    # Shutdown (if needed)

app = FastAPI(
    title="AI Email Subject Line Optimizer",
    description="Generate and A/B test email subject line variations using AI",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Services
subject_service = SubjectGeneratorService()
ab_testing_service = MultiArmedBanditService()
analytics_service = AnalyticsService()

@app.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """Health check endpoint"""
    try:
        # Check database
        async with AsyncSessionLocal() as session:
            await session.execute("SELECT 1")
        db_status = "healthy"
    except Exception:
        db_status = "unhealthy"
    
    # Check cache
    try:
        await cache_manager.get("health_check")
        cache_status = "healthy"
    except Exception:
        cache_status = "unhealthy"
    
    return HealthCheckResponse(
        status="healthy" if db_status == "healthy" and cache_status == "healthy" else "degraded",
        database=db_status,
        cache=cache_status
    )

@app.post("/generate", response_model=SubjectGenerationResponse)
async def generate_subject_lines(
    request: SubjectGenerationRequest,
    db: AsyncSession = Depends(get_db)
):
    """Generate AI-optimized subject line variations"""
    try:
        result = await subject_service.generate_subject_variations(
            email_content=request.email_content,
            original_subject=request.original_subject
        )
        
        return SubjectGenerationResponse(
            ab_test_id=result["ab_test_id"],
            variations=result["variations"],
            cached=result["cached"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Subject generation failed: {str(e)}")

@app.post("/track", response_model=EventTrackingResponse)
async def track_event(
    request: EventTrackingRequest,
    client_request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Track email events (sent, opened, clicked)"""
    try:
        # Extract client info
        user_agent = request.user_agent or client_request.headers.get("User-Agent")
        ip_address = request.ip_address or client_request.client.host
        
        await ab_testing_service.record_event(
            variation_id=request.variation_id,
            event_type=request.event_type,
            session=db,
            user_agent=user_agent,
            ip_address=ip_address
        )
        
        return EventTrackingResponse(
            success=True,
            message=f"Event '{request.event_type}' tracked successfully"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Event tracking failed: {str(e)}")

@app.get("/select/{ab_test_id}")
async def select_best_variation(
    ab_test_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Select the best performing variation using multi-armed bandit"""
    try:
        variation = await ab_testing_service.select_best_variation(ab_test_id, db)
        
        if not variation:
            raise HTTPException(status_code=404, detail="A/B test not found")
        
        # Update selection count
        variation.times_selected += 1
        await db.commit()
        
        return {
            "variation_id": str(variation.id),
            "subject_line": variation.subject_line,
            "variation_index": variation.variation_index
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Variation selection failed: {str(e)}")

@app.get("/analytics/{ab_test_id}", response_model=TestPerformanceResponse)
async def get_test_performance(
    ab_test_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get performance analytics for an A/B test"""
    try:
        performance = await analytics_service.get_test_performance(ab_test_id, db)
        
        if "error" in performance:
            raise HTTPException(status_code=404, detail=performance["error"])
        
        return TestPerformanceResponse(**performance)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analytics retrieval failed: {str(e)}")

@app.get("/analytics/top-subjects", response_model=List[TopPerformingSubject])
async def get_top_subjects(
    limit: int = 10,
    days: int = 30,
    db: AsyncSession = Depends(get_db)
):
    """Get top performing subject lines"""
    try:
        subjects = await analytics_service.get_top_performing_subjects(db, limit, days)
        return [TopPerformingSubject(**subject) for subject in subjects]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Top subjects retrieval failed: {str(e)}")

@app.get("/analytics/dashboard", response_model=DashboardMetrics)
async def get_dashboard_metrics(db: AsyncSession = Depends(get_db)):
    """Get dashboard metrics"""
    try:
        metrics = await analytics_service.get_dashboard_metrics(db)
        return DashboardMetrics(**metrics)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dashboard metrics retrieval failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
```

#### 3. Environment Configuration
**File**: `src/config/settings.py`
**Changes**: Centralized settings management

```python
import os
from typing import Optional

class Settings:
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./data/email_optimizer.db")
    
    # Redis Cache
    REDIS_URL: Optional[str] = os.getenv("REDIS_URL")
    CACHE_TTL: int = int(os.getenv("CACHE_TTL", "3600"))
    
    # AI Providers
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    ANTHROPIC_API_KEY: Optional[str] = os.getenv("ANTHROPIC_API_KEY")
    
    # A/B Testing
    MIN_SAMPLES_FOR_BANDIT: int = int(os.getenv("MIN_SAMPLES_FOR_BANDIT", "5000"))
    CONFIDENCE_LEVEL: float = float(os.getenv("CONFIDENCE_LEVEL", "0.95"))
    
    # Rate Limiting
    RATE_LIMIT_INITIAL_DELAY: float = float(os.getenv("RATE_LIMIT_INITIAL_DELAY", "1.0"))
    RATE_LIMIT_MAX_DELAY: float = float(os.getenv("RATE_LIMIT_MAX_DELAY", "60.0"))
    RATE_LIMIT_MAX_RETRIES: int = int(os.getenv("RATE_LIMIT_MAX_RETRIES", "5"))

settings = Settings()
```

### Success Criteria:

#### Automated Verification:
- [ ] FastAPI app imports successfully: `python -c "from src.main import app; print('App created')"`
- [ ] API models validate properly: `python -c "from src.api.models import SubjectGenerationRequest; req = SubjectGenerationRequest(email_content='Test email content'); print('Validation passed')"`
- [ ] Health endpoint responds: `python -m pytest tests/test_api.py::test_health_endpoint -v`
- [ ] Server starts without errors: `timeout 5s uvicorn src.main:app --port 8001 || echo 'Server startup test complete'`

#### Manual Verification:
- [ ] POST /generate returns 5 subject line variations ≤60 characters
- [ ] POST /track successfully records sent/opened/clicked events
- [ ] GET /select/{test_id} returns optimal variation via multi-armed bandit
- [ ] GET /analytics/{test_id} shows performance metrics with confidence intervals
- [ ] GET /analytics/top-subjects shows best performing subjects from recent tests
- [ ] API validates input parameters and returns appropriate error messages

---

## Phase 5: Testing & Documentation

### Overview
Implement comprehensive test suite covering unit tests, integration tests, and API tests with proper async patterns.

### Changes Required:

#### 1. Unit Tests
**File**: `tests/__init__.py`
**Changes**: Create tests package

```python
# Empty __init__.py for tests package
```

**File**: `tests/test_models.py`
**Changes**: Test database models

```python
import pytest
import asyncio
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from src.models.ab_testing import Base, ABTest, TestVariation, EmailEvent

@pytest.fixture
async def async_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with AsyncSessionLocal() as session:
        yield session

@pytest.mark.asyncio
async def test_ab_test_creation(async_session):
    ab_test = ABTest(
        id="test123",
        email_content_hash="hash123",
        original_subject="Test Subject"
    )
    async_session.add(ab_test)
    await async_session.commit()
    
    assert ab_test.id == "test123"
    assert ab_test.is_active is True
    assert isinstance(ab_test.created_at, datetime)

@pytest.mark.asyncio
async def test_test_variation_creation(async_session):
    ab_test = ABTest(id="test123", email_content_hash="hash123")
    async_session.add(ab_test)
    
    variation = TestVariation(
        ab_test_id="test123",
        subject_line="Optimized Subject",
        variation_index=0
    )
    async_session.add(variation)
    await async_session.commit()
    
    assert variation.subject_line == "Optimized Subject"
    assert variation.variation_index == 0
    assert variation.times_sent == 0
```

**File**: `tests/test_services.py`
**Changes**: Test service layer

```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.services.ai_providers import OpenAIProvider, AnthropicProvider, RateLimitConfig
from src.services.ab_testing import MultiArmedBanditService
from src.models.ab_testing import TestVariation

class TestAIProviders:
    @pytest.fixture
    def rate_limit_config(self):
        return RateLimitConfig(initial_delay=0.1, max_delay=1.0, max_retries=2)
    
    @pytest.mark.asyncio
    async def test_openai_subject_generation(self, rate_limit_config):
        with patch('openai.AsyncOpenAI') as mock_openai:
            # Mock the response
            mock_response = MagicMock()
            mock_response.choices[0].message.content = """
            1. Amazing Deal Inside!
            2. Don't Miss Out - Limited Time
            3. Your Exclusive Offer Awaits
            4. Last Chance - Act Now!
            5. Special Savings Just for You
            """
            
            mock_client = AsyncMock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_openai.return_value = mock_client
            
            provider = OpenAIProvider("test-key", rate_limit_config)
            provider.client = mock_client
            
            result = await provider.generate_subject_lines("Test email content")
            
            assert len(result) == 5
            assert all(len(subject) <= 60 for subject in result)
            assert "Amazing Deal Inside!" in result

class TestMultiArmedBandit:
    @pytest.fixture
    def bandit_service(self):
        return MultiArmedBanditService(confidence_level=0.95, min_samples=100)
    
    def test_round_robin_selection(self, bandit_service):
        variations = [
            TestVariation(times_selected=5, subject_line="A"),
            TestVariation(times_selected=3, subject_line="B"),
            TestVariation(times_selected=7, subject_line="C"),
        ]
        
        selected = bandit_service._round_robin_selection(variations)
        assert selected.subject_line == "B"  # Least selected
    
    def test_thompson_sampling(self, bandit_service):
        variations = [
            TestVariation(clicks=10, times_sent=100, subject_line="A"),
            TestVariation(clicks=15, times_sent=100, subject_line="B"),  # Better performer
            TestVariation(clicks=5, times_sent=100, subject_line="C"),
        ]
        
        # Run multiple times to check probabilistic selection
        selections = []
        for _ in range(100):
            selected = bandit_service._thompson_sampling(variations)
            selections.append(selected.subject_line)
        
        # B should be selected most often due to higher click rate
        assert selections.count("B") > selections.count("A")
        assert selections.count("B") > selections.count("C")
```

**File**: `tests/test_api.py`
**Changes**: Test API endpoints

```python
import pytest
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock
from src.main import app

@pytest.mark.asyncio
async def test_health_endpoint():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/health")
    
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "timestamp" in data

@pytest.mark.asyncio
async def test_generate_subject_lines():
    with patch('src.services.subject_generator.SubjectGeneratorService.generate_subject_variations') as mock_generate:
        mock_generate.return_value = {
            "ab_test_id": "test123",
            "variations": [
                {"id": "var1", "subject_line": "Great Subject 1", "variation_index": 0},
                {"id": "var2", "subject_line": "Great Subject 2", "variation_index": 1},
                {"id": "var3", "subject_line": "Great Subject 3", "variation_index": 2},
                {"id": "var4", "subject_line": "Great Subject 4", "variation_index": 3},
                {"id": "var5", "subject_line": "Great Subject 5", "variation_index": 4},
            ],
            "cached": False
        }
        
        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.post("/generate", json={
                "email_content": "This is a test email with some content to generate subjects for.",
                "original_subject": "Original Subject"
            })
        
        assert response.status_code == 200
        data = response.json()
        assert data["ab_test_id"] == "test123"
        assert len(data["variations"]) == 5
        assert all(len(var["subject_line"]) <= 60 for var in data["variations"])

@pytest.mark.asyncio
async def test_track_event():
    with patch('src.services.ab_testing.MultiArmedBanditService.record_event') as mock_record:
        mock_record.return_value = None
        
        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.post("/track", json={
                "variation_id": "var123",
                "event_type": "clicked"
            })
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

@pytest.mark.asyncio
async def test_generate_validation_error():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post("/generate", json={
            "email_content": ""  # Invalid: too short
        })
    
    assert response.status_code == 422  # Validation error
```

#### 2. Integration Tests
**File**: `tests/test_integration.py`
**Changes**: End-to-end integration tests

```python
import pytest
import asyncio
from httpx import AsyncClient
from src.main import app
from src.config.database import create_tables

@pytest.mark.asyncio
async def test_full_workflow():
    """Test complete workflow: generate -> select -> track -> analytics"""
    # Setup
    await create_tables()
    
    async with AsyncClient(app=app, base_url="http://test") as ac:
        # 1. Generate subject lines
        generate_response = await ac.post("/generate", json={
            "email_content": "This is a comprehensive test email with substantial content to ensure proper subject line generation and testing workflow validation."
        })
        
        assert generate_response.status_code == 200
        generate_data = generate_response.json()
        ab_test_id = generate_data["ab_test_id"]
        variation_id = generate_data["variations"][0]["id"]
        
        # 2. Select best variation (initially random due to no data)
        select_response = await ac.get(f"/select/{ab_test_id}")
        assert select_response.status_code == 200
        
        # 3. Track events
        events = ["sent", "opened", "clicked"]
        for event in events:
            track_response = await ac.post("/track", json={
                "variation_id": variation_id,
                "event_type": event
            })
            assert track_response.status_code == 200
        
        # 4. Get analytics
        analytics_response = await ac.get(f"/analytics/{ab_test_id}")
        assert analytics_response.status_code == 200
        analytics_data = analytics_response.json()
        assert analytics_data["test_id"] == ab_test_id
        
        # 5. Check dashboard metrics
        dashboard_response = await ac.get("/analytics/dashboard")
        assert dashboard_response.status_code == 200
        dashboard_data = dashboard_response.json()
        assert dashboard_data["total_tests"] >= 1
```

#### 3. Test Configuration
**File**: `pytest.ini`
**Changes**: Pytest configuration

```ini
[tool:pytest]
asyncio_mode = auto
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    --verbose
    --tb=short
    --cov=src
    --cov-report=html:htmlcov
    --cov-report=term-missing
    --cov-fail-under=80
```

### Success Criteria:

#### Automated Verification:
- [ ] All unit tests pass: `pytest tests/test_models.py tests/test_services.py -v`
- [ ] API tests pass: `pytest tests/test_api.py -v`
- [ ] Integration tests pass: `pytest tests/test_integration.py -v`
- [ ] Code coverage meets 80% threshold: `pytest --cov=src --cov-fail-under=80`
- [ ] No linting errors: `flake8 src tests`

#### Manual Verification:
- [ ] Tests cover all critical paths including error conditions
- [ ] Async test patterns work correctly with SQLAlchemy and FastAPI
- [ ] Integration tests validate complete user workflows
- [ ] Mock objects properly simulate external dependencies (AI APIs)
- [ ] Test database isolation prevents test interference

---

## Testing Strategy

### Unit Tests:
- Database model creation and relationships
- AI provider response parsing and error handling
- Multi-armed bandit algorithm selection logic
- Cache hit/miss behavior with SHA256 hashing
- Rate limiting with exponential backoff and jitter

### Integration Tests:
- Complete API workflow from generation to analytics
- Database transactions with proper async session handling
- Redis cache integration with fallback to disk cache
- Multi-armed bandit selection with real database updates

### Manual Testing Steps:
1. Start the application with `uvicorn src.main:app --reload`
2. Test subject generation with various email content lengths
3. Verify caching by sending identical requests (should return cached=true)
4. Track events and verify analytics reflect the changes
5. Test with both OpenAI and Anthropic API keys configured
6. Validate error handling with invalid requests and network issues

## Performance Considerations

- Connection pooling configured for 20-30 concurrent connections
- Redis caching reduces AI API calls by ~50% for duplicate content
- SHA256 hashing provides fast, collision-resistant cache keys
- Async architecture throughout prevents blocking operations
- Multi-armed bandit minimizes suboptimal subject line selection
- Temperature 0.85 balances creativity with consistency in AI generation

## Migration Notes

- Database schema uses UUID and string primary keys for scalability
- SQLAlchemy 2.0 async patterns ensure future compatibility
- Environment variables allow easy deployment configuration changes
- Graceful fallback from Redis to disk cache ensures availability
- Both OpenAI and Anthropic supported for provider flexibility

## References

- Original ticket: `docs/tickets/ticket_001_initial_setup.md`
- Research findings: Multi-armed bandit with Thompson sampling, 95% confidence intervals
- Architecture: FastAPI async + SQLAlchemy 2.0 + Redis caching + AI integration
- Performance targets: 50% cache hit rate, ≤60 character subjects, 5000 email minimum for bandit activation