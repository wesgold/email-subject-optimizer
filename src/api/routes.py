from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func

from src.config.database import get_db
from src.config.cache import cache_manager
from src.services.subject_generator import SubjectGeneratorService
from src.models.ab_testing import ABTest, TestVariation, EmailEvent
from src.api.models import (
    GenerateRequest, GenerateResponse, SubjectVariation,
    TrackRequest, TrackResponse,
    AnalyticsResponse, TopPerformingSubject,
    DashboardMetrics, HealthCheckResponse
)
from datetime import datetime, timedelta

router = APIRouter(prefix="/api", tags=["api"])

subject_service = SubjectGeneratorService()

@router.get("/health", response_model=HealthCheckResponse)
async def health_check(db: AsyncSession = Depends(get_db)):
    """Health check endpoint"""
    try:
        await db.execute(select(func.count()).select_from(ABTest))
        db_status = "healthy"
    except Exception:
        db_status = "unhealthy"
    
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

@router.post("/generate", response_model=GenerateResponse)
async def generate_subject_lines(
    request: GenerateRequest,
    db: AsyncSession = Depends(get_db)
):
    """Generate AI-optimized subject line variations"""
    try:
        result = await subject_service.generate_subject_variations(
            email_content=request.email_content,
            original_subject=request.original_subject
        )
        
        variations = [
            SubjectVariation(
                id=v["id"],
                subject_line=v["subject_line"],
                variation_index=v["variation_index"]
            )
            for v in result["variations"]
        ]
        
        return GenerateResponse(
            ab_test_id=result["ab_test_id"],
            variations=variations,
            cached=result["cached"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Subject generation failed: {str(e)}")

@router.post("/track", response_model=TrackResponse)
async def track_event(
    request: TrackRequest,
    client_request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Track email events (sent, opened, clicked)"""
    try:
        user_agent = request.user_agent or client_request.headers.get("User-Agent")
        ip_address = request.ip_address or client_request.client.host if client_request.client else None
        
        event = EmailEvent(
            variation_id=request.variation_id,
            event_type=request.event_type,
            user_agent=user_agent,
            ip_address=ip_address
        )
        db.add(event)
        
        if request.event_type == "sent":
            await db.execute(
                update(TestVariation)
                .where(TestVariation.id == request.variation_id)
                .values(times_sent=TestVariation.times_sent + 1)
            )
        elif request.event_type == "opened":
            await db.execute(
                update(TestVariation)
                .where(TestVariation.id == request.variation_id)
                .values(opens=TestVariation.opens + 1)
            )
        elif request.event_type == "clicked":
            await db.execute(
                update(TestVariation)
                .where(TestVariation.id == request.variation_id)
                .values(clicks=TestVariation.clicks + 1)
            )
        
        await db.commit()
        
        return TrackResponse(
            success=True,
            message=f"Event '{request.event_type}' tracked successfully"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Event tracking failed: {str(e)}")

@router.get("/analytics/{ab_test_id}", response_model=AnalyticsResponse)
async def get_test_analytics(
    ab_test_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get performance analytics for an A/B test"""
    try:
        test_result = await db.execute(
            select(ABTest).where(ABTest.id == ab_test_id)
        )
        test = test_result.scalar_one_or_none()
        
        if not test:
            raise HTTPException(status_code=404, detail="A/B test not found")
        
        variations_result = await db.execute(
            select(TestVariation).where(TestVariation.ab_test_id == ab_test_id)
        )
        variations = variations_result.scalars().all()
        
        variations_data = []
        for variation in variations:
            open_rate = (variation.opens / variation.times_sent) if variation.times_sent > 0 else 0
            click_rate = (variation.clicks / variation.times_sent) if variation.times_sent > 0 else 0
            
            variations_data.append({
                "id": str(variation.id),
                "subject_line": variation.subject_line,
                "variation_index": variation.variation_index,
                "times_sent": variation.times_sent,
                "opens": variation.opens,
                "clicks": variation.clicks,
                "open_rate": round(open_rate * 100, 2),
                "click_rate": round(click_rate * 100, 2)
            })
        
        return AnalyticsResponse(
            test_id=ab_test_id,
            created_at=test.created_at.isoformat(),
            original_subject=test.original_subject,
            is_active=test.is_active,
            variations=variations_data
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analytics retrieval failed: {str(e)}")