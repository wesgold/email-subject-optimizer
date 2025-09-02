from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from uuid import UUID

from src.config.database import get_db
from src.config.cache import cache_manager
from src.services.subject_generator import SubjectGeneratorService
from src.services.ab_testing import MultiArmedBanditService
from src.services.analytics import AnalyticsService
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

@router.get("/select/{ab_test_id}")
async def select_variation(
    ab_test_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Select the best variation using multi-armed bandit algorithm"""
    try:
        test_uuid = UUID(ab_test_id)
        bandit_service = MultiArmedBanditService(db)
        result = await bandit_service.select_variation(test_uuid)
        
        if not result:
            raise HTTPException(status_code=404, detail="Test not found or not active")
        
        return result
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Variation selection failed: {str(e)}")

@router.post("/record-event/{variation_id}")
async def record_event(
    variation_id: str,
    event_type: str,
    db: AsyncSession = Depends(get_db)
):
    """Record an event for a variation"""
    try:
        variation_uuid = UUID(variation_id)
        bandit_service = MultiArmedBanditService(db)
        success = await bandit_service.record_event(
            variation_uuid,
            event_type,
            metadata={}
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Variation not found")
        
        return {"success": True, "message": f"Event {event_type} recorded"}
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Event recording failed: {str(e)}")

@router.get("/analytics/top-subjects")
async def get_top_subjects(
    limit: int = Query(10, ge=1, le=100),
    days: int = Query(30, ge=1, le=365),
    min_sends: int = Query(100, ge=1),
    db: AsyncSession = Depends(get_db)
):
    """Get top performing subject lines"""
    try:
        analytics_service = AnalyticsService(db)
        results = await analytics_service.get_top_performing_subjects(
            limit=limit,
            days=days,
            min_sends=min_sends
        )
        return {"top_subjects": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve top subjects: {str(e)}")

@router.get("/analytics/dashboard")
async def get_dashboard_metrics(db: AsyncSession = Depends(get_db)):
    """Get comprehensive dashboard metrics"""
    try:
        analytics_service = AnalyticsService(db)
        metrics = await analytics_service.get_dashboard_metrics()
        return metrics
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve dashboard metrics: {str(e)}")

@router.get("/analytics/variation/{variation_id}")
async def get_variation_performance(
    variation_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get detailed performance metrics for a specific variation"""
    try:
        variation_uuid = UUID(variation_id)
        analytics_service = AnalyticsService(db)
        result = await analytics_service.get_variation_performance(variation_uuid)
        
        if not result:
            raise HTTPException(status_code=404, detail="Variation not found")
        
        return result
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve variation performance: {str(e)}")

@router.get("/analytics/test-comparison/{ab_test_id}")
async def get_test_comparison(
    ab_test_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get comparative analysis of all variations in a test"""
    try:
        test_uuid = UUID(ab_test_id)
        analytics_service = AnalyticsService(db)
        result = await analytics_service.get_test_comparison(test_uuid)
        
        if not result:
            raise HTTPException(status_code=404, detail="Test not found")
        
        return result
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve test comparison: {str(e)}")