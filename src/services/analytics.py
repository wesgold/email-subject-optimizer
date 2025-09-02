"""Analytics Service for Email Subject Line Performance.

Provides comprehensive analytics for A/B testing performance,
including top performers, dashboard metrics, and detailed insights.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc
from uuid import UUID

from src.models.ab_testing import ABTest, ABTestVariation, ABTestEvent
from src.utils.logging import logger


class AnalyticsService:
    """Service for analyzing A/B test performance and metrics."""
    
    def __init__(self, session: AsyncSession):
        """Initialize the analytics service.
        
        Args:
            session: Database session
        """
        self.session = session
    
    async def get_top_performing_subjects(
        self,
        limit: int = 10,
        days: int = 30,
        min_sends: int = 100
    ) -> List[Dict[str, Any]]:
        """Get top performing subject lines by conversion rate.
        
        Args:
            limit: Maximum number of results
            days: Number of days to look back
            min_sends: Minimum number of sends required
            
        Returns:
            List of top performing subject lines with metrics
        """
        # Calculate date threshold
        date_threshold = datetime.utcnow() - timedelta(days=days)
        
        # Query for top performing variations
        stmt = (
            select(ABTestVariation)
            .join(ABTest)
            .where(
                and_(
                    ABTestVariation.times_sent >= min_sends,
                    ABTest.created_at >= date_threshold
                )
            )
            .order_by(desc(ABTestVariation.conversion_rate))
            .limit(limit)
        )
        
        result = await self.session.execute(stmt)
        variations = result.scalars().all()
        
        # Format results
        top_performers = []
        for variation in variations:
            # Get test details
            stmt = select(ABTest).where(ABTest.id == variation.ab_test_id)
            result = await self.session.execute(stmt)
            test = result.scalar_one()
            
            top_performers.append({
                "subject_line": variation.subject_line,
                "test_name": test.name,
                "test_id": str(test.id),
                "variation_id": str(variation.id),
                "metrics": {
                    "times_sent": variation.times_sent,
                    "opens": variation.opens,
                    "clicks": variation.clicks,
                    "conversions": variation.conversions,
                    "open_rate": variation.open_rate,
                    "click_rate": variation.click_rate,
                    "conversion_rate": variation.conversion_rate
                },
                "created_at": variation.created_at.isoformat()
            })
        
        return top_performers
    
    async def get_dashboard_metrics(self) -> Dict[str, Any]:
        """Get comprehensive dashboard metrics.
        
        Returns:
            Dashboard metrics including totals, averages, and recent performance
        """
        # Get total tests
        stmt = select(func.count(ABTest.id))
        result = await self.session.execute(stmt)
        total_tests = result.scalar() or 0
        
        # Get active tests
        stmt = select(func.count(ABTest.id)).where(ABTest.status == 'active')
        result = await self.session.execute(stmt)
        active_tests = result.scalar() or 0
        
        # Get completed tests
        stmt = select(func.count(ABTest.id)).where(ABTest.status == 'completed')
        result = await self.session.execute(stmt)
        completed_tests = result.scalar() or 0
        
        # Get total variations
        stmt = select(func.count(ABTestVariation.id))
        result = await self.session.execute(stmt)
        total_variations = result.scalar() or 0
        
        # Calculate overall metrics
        stmt = select(
            func.sum(ABTestVariation.times_sent),
            func.sum(ABTestVariation.opens),
            func.sum(ABTestVariation.clicks),
            func.sum(ABTestVariation.conversions)
        )
        result = await self.session.execute(stmt)
        totals = result.one()
        
        total_sends = totals[0] or 0
        total_opens = totals[1] or 0
        total_clicks = totals[2] or 0
        total_conversions = totals[3] or 0
        
        # Calculate rates
        overall_open_rate = total_opens / max(1, total_sends)
        overall_click_rate = total_clicks / max(1, total_sends)
        overall_conversion_rate = total_conversions / max(1, total_sends)
        
        # Get recent performance (last 7 days)
        recent_threshold = datetime.utcnow() - timedelta(days=7)
        stmt = (
            select(
                func.sum(ABTestVariation.times_sent),
                func.sum(ABTestVariation.opens),
                func.sum(ABTestVariation.clicks),
                func.sum(ABTestVariation.conversions)
            )
            .join(ABTest)
            .where(ABTest.created_at >= recent_threshold)
        )
        result = await self.session.execute(stmt)
        recent = result.one()
        
        recent_sends = recent[0] or 0
        recent_opens = recent[1] or 0
        recent_clicks = recent[2] or 0
        recent_conversions = recent[3] or 0
        
        recent_open_rate = recent_opens / max(1, recent_sends) if recent_sends > 0 else 0
        recent_click_rate = recent_clicks / max(1, recent_sends) if recent_sends > 0 else 0
        recent_conversion_rate = recent_conversions / max(1, recent_sends) if recent_sends > 0 else 0
        
        # Get top performer
        stmt = (
            select(ABTestVariation)
            .where(ABTestVariation.times_sent >= 100)
            .order_by(desc(ABTestVariation.conversion_rate))
            .limit(1)
        )
        result = await self.session.execute(stmt)
        top_variation = result.scalar_one_or_none()
        
        top_performer = None
        if top_variation:
            top_performer = {
                "subject_line": top_variation.subject_line,
                "conversion_rate": top_variation.conversion_rate,
                "times_sent": top_variation.times_sent
            }
        
        return {
            "tests": {
                "total": total_tests,
                "active": active_tests,
                "completed": completed_tests
            },
            "variations": {
                "total": total_variations
            },
            "overall_metrics": {
                "total_sends": total_sends,
                "total_opens": total_opens,
                "total_clicks": total_clicks,
                "total_conversions": total_conversions,
                "open_rate": overall_open_rate,
                "click_rate": overall_click_rate,
                "conversion_rate": overall_conversion_rate
            },
            "recent_performance": {
                "period": "last_7_days",
                "sends": recent_sends,
                "opens": recent_opens,
                "clicks": recent_clicks,
                "conversions": recent_conversions,
                "open_rate": recent_open_rate,
                "click_rate": recent_click_rate,
                "conversion_rate": recent_conversion_rate
            },
            "top_performer": top_performer,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def get_variation_performance(
        self,
        variation_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """Get detailed performance metrics for a specific variation.
        
        Args:
            variation_id: The variation ID
            
        Returns:
            Detailed performance metrics
        """
        # Get variation
        stmt = select(ABTestVariation).where(ABTestVariation.id == variation_id)
        result = await self.session.execute(stmt)
        variation = result.scalar_one_or_none()
        
        if not variation:
            return None
        
        # Get test details
        stmt = select(ABTest).where(ABTest.id == variation.ab_test_id)
        result = await self.session.execute(stmt)
        test = result.scalar_one()
        
        # Get recent events (last 24 hours)
        recent_threshold = datetime.utcnow() - timedelta(hours=24)
        stmt = (
            select(
                ABTestEvent.event_type,
                func.count(ABTestEvent.id)
            )
            .where(
                and_(
                    ABTestEvent.variation_id == variation_id,
                    ABTestEvent.created_at >= recent_threshold
                )
            )
            .group_by(ABTestEvent.event_type)
        )
        result = await self.session.execute(stmt)
        recent_events = dict(result.all())
        
        # Calculate confidence interval using Wilson score
        from src.services.ab_testing import MultiArmedBanditService
        bandit = MultiArmedBanditService(self.session)
        confidence_interval = bandit._calculate_wilson_score(
            variation.conversions,
            variation.times_sent
        )
        
        return {
            "variation_id": str(variation_id),
            "subject_line": variation.subject_line,
            "test": {
                "id": str(test.id),
                "name": test.name,
                "status": test.status
            },
            "lifetime_metrics": {
                "times_selected": variation.times_selected,
                "times_sent": variation.times_sent,
                "opens": variation.opens,
                "clicks": variation.clicks,
                "conversions": variation.conversions,
                "open_rate": variation.open_rate,
                "click_rate": variation.click_rate,
                "conversion_rate": variation.conversion_rate,
                "confidence_interval": confidence_interval
            },
            "recent_activity": {
                "period": "last_24_hours",
                "events": recent_events
            },
            "created_at": variation.created_at.isoformat(),
            "updated_at": variation.updated_at.isoformat()
        }
    
    async def get_test_comparison(
        self,
        ab_test_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """Get comparative analysis of all variations in a test.
        
        Args:
            ab_test_id: The A/B test ID
            
        Returns:
            Comparative analysis with winner identification
        """
        # Get test
        stmt = select(ABTest).where(ABTest.id == ab_test_id)
        result = await self.session.execute(stmt)
        test = result.scalar_one_or_none()
        
        if not test:
            return None
        
        # Get all variations
        stmt = (
            select(ABTestVariation)
            .where(ABTestVariation.ab_test_id == ab_test_id)
            .order_by(desc(ABTestVariation.conversion_rate))
        )
        result = await self.session.execute(stmt)
        variations = result.scalars().all()
        
        if not variations:
            return None
        
        # Calculate confidence intervals
        from src.services.ab_testing import MultiArmedBanditService
        bandit = MultiArmedBanditService(self.session)
        
        variations_data = []
        for variation in variations:
            confidence_interval = bandit._calculate_wilson_score(
                variation.conversions,
                variation.times_sent
            )
            
            variations_data.append({
                "id": str(variation.id),
                "subject_line": variation.subject_line,
                "metrics": {
                    "times_sent": variation.times_sent,
                    "conversion_rate": variation.conversion_rate,
                    "confidence_interval": confidence_interval
                }
            })
        
        # Identify winner (highest lower bound of confidence interval)
        winner = None
        if variations[0].times_sent >= 100:  # Minimum sample size
            winner = {
                "id": str(variations[0].id),
                "subject_line": variations[0].subject_line,
                "conversion_rate": variations[0].conversion_rate,
                "improvement": 0.0
            }
            
            # Calculate improvement over average
            if len(variations) > 1:
                avg_conversion = sum(v.conversion_rate for v in variations[1:]) / len(variations[1:])
                if avg_conversion > 0:
                    winner["improvement"] = (
                        (variations[0].conversion_rate - avg_conversion) / avg_conversion
                    ) * 100
        
        return {
            "test_id": str(ab_test_id),
            "test_name": test.name,
            "status": test.status,
            "total_variations": len(variations),
            "total_samples": sum(v.times_sent for v in variations),
            "variations": variations_data,
            "winner": winner,
            "created_at": test.created_at.isoformat()
        }