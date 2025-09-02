"""Multi-Armed Bandit Service for A/B Testing.

Implements Thompson sampling algorithm for optimal subject line selection
with exploration and exploitation phases.
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
import numpy as np
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
import math

from src.models.ab_testing import ABTest, ABTestVariation, ABTestEvent
from src.utils.logging import logger


class MultiArmedBanditService:
    """Multi-armed bandit service for A/B test variation selection."""
    
    EXPLORATION_THRESHOLD = 5000  # Total samples before switching to exploitation
    CONFIDENCE_LEVEL = 0.95  # 95% confidence interval
    
    def __init__(self, session: AsyncSession):
        """Initialize the service.
        
        Args:
            session: Database session
        """
        self.session = session
    
    async def select_variation(self, ab_test_id: UUID) -> Optional[Dict[str, Any]]:
        """Select the best variation using Thompson sampling.
        
        Uses round-robin during exploration phase (< 5000 total samples),
        then switches to Thompson sampling for exploitation.
        
        Args:
            ab_test_id: The A/B test ID
            
        Returns:
            Selected variation with metadata
        """
        # Get test and variations
        stmt = select(ABTest).where(ABTest.id == ab_test_id)
        result = await self.session.execute(stmt)
        test = result.scalar_one_or_none()
        
        if not test or test.status != 'active':
            logger.warning(f"Test {ab_test_id} not found or not active")
            return None
        
        # Get all variations for this test
        stmt = select(ABTestVariation).where(
            ABTestVariation.ab_test_id == ab_test_id
        ).order_by(ABTestVariation.created_at)
        result = await self.session.execute(stmt)
        variations = result.scalars().all()
        
        if not variations:
            logger.warning(f"No variations found for test {ab_test_id}")
            return None
        
        # Calculate total samples across all variations
        total_samples = sum(v.times_selected for v in variations)
        
        # Select variation based on phase
        if total_samples < self.EXPLORATION_THRESHOLD:
            # Exploration phase: Round-robin selection
            selected_variation = self._round_robin_select(variations)
            selection_method = "round_robin"
        else:
            # Exploitation phase: Thompson sampling
            selected_variation = self._thompson_sampling_select(variations)
            selection_method = "thompson_sampling"
        
        # Update selection count
        selected_variation.times_selected += 1
        await self.session.commit()
        
        # Calculate confidence interval
        confidence_interval = self._calculate_wilson_score(
            selected_variation.conversions,
            selected_variation.times_sent
        )
        
        return {
            "id": str(selected_variation.id),
            "subject_line": selected_variation.subject_line,
            "ab_test_id": str(ab_test_id),
            "selection_method": selection_method,
            "performance": {
                "open_rate": selected_variation.open_rate,
                "click_rate": selected_variation.click_rate,
                "conversion_rate": selected_variation.conversion_rate,
                "confidence_interval": confidence_interval,
                "times_selected": selected_variation.times_selected,
                "times_sent": selected_variation.times_sent
            }
        }
    
    def _round_robin_select(self, variations: List[ABTestVariation]) -> ABTestVariation:
        """Select variation using round-robin strategy.
        
        Args:
            variations: List of variations
            
        Returns:
            Selected variation
        """
        # Find variation with minimum selections
        min_selections = min(v.times_selected for v in variations)
        candidates = [v for v in variations if v.times_selected == min_selections]
        
        # Return first candidate (earliest created)
        return candidates[0]
    
    def _thompson_sampling_select(self, variations: List[ABTestVariation]) -> ABTestVariation:
        """Select variation using Thompson sampling with Beta distribution.
        
        Args:
            variations: List of variations
            
        Returns:
            Selected variation
        """
        best_variation = None
        best_sample = -1
        
        for variation in variations:
            # Beta distribution parameters
            # alpha = successes + 1, beta = failures + 1
            alpha = variation.conversions + 1
            beta = max(1, variation.times_sent - variation.conversions) + 1
            
            # Sample from Beta distribution
            sample = np.random.beta(alpha, beta)
            
            if sample > best_sample:
                best_sample = sample
                best_variation = variation
        
        return best_variation
    
    def _calculate_wilson_score(self, successes: int, trials: int) -> Dict[str, float]:
        """Calculate Wilson score confidence interval.
        
        Args:
            successes: Number of successful conversions
            trials: Total number of trials
            
        Returns:
            Dictionary with lower and upper bounds
        """
        if trials == 0:
            return {"lower": 0.0, "upper": 0.0}
        
        # Wilson score formula
        p_hat = successes / trials
        z = 1.96  # 95% confidence level
        
        denominator = 1 + z**2 / trials
        
        center = (p_hat + z**2 / (2 * trials)) / denominator
        
        margin = z * math.sqrt(
            (p_hat * (1 - p_hat) + z**2 / (4 * trials)) / trials
        ) / denominator
        
        return {
            "lower": max(0.0, center - margin),
            "upper": min(1.0, center + margin)
        }
    
    async def record_event(
        self,
        variation_id: UUID,
        event_type: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Record an event and update variation statistics.
        
        Args:
            variation_id: The variation ID
            event_type: Type of event (send, open, click, conversion)
            metadata: Optional event metadata
            
        Returns:
            True if successful
        """
        try:
            # Get variation
            stmt = select(ABTestVariation).where(ABTestVariation.id == variation_id)
            result = await self.session.execute(stmt)
            variation = result.scalar_one_or_none()
            
            if not variation:
                logger.warning(f"Variation {variation_id} not found")
                return False
            
            # Create event record
            event = ABTestEvent(
                ab_test_id=variation.ab_test_id,
                variation_id=variation_id,
                event_type=event_type,
                event_metadata=metadata or {}
            )
            self.session.add(event)
            
            # Update variation statistics
            if event_type == "send":
                variation.times_sent += 1
            elif event_type == "open":
                variation.opens += 1
                variation.open_rate = variation.opens / max(1, variation.times_sent)
            elif event_type == "click":
                variation.clicks += 1
                variation.click_rate = variation.clicks / max(1, variation.times_sent)
            elif event_type == "conversion":
                variation.conversions += 1
                variation.conversion_rate = variation.conversions / max(1, variation.times_sent)
            
            await self.session.commit()
            logger.info(f"Recorded {event_type} event for variation {variation_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error recording event: {e}")
            await self.session.rollback()
            return False
    
    async def get_test_performance(self, ab_test_id: UUID) -> Optional[Dict[str, Any]]:
        """Get performance metrics for all variations in a test.
        
        Args:
            ab_test_id: The A/B test ID
            
        Returns:
            Performance metrics for all variations
        """
        # Get test
        stmt = select(ABTest).where(ABTest.id == ab_test_id)
        result = await self.session.execute(stmt)
        test = result.scalar_one_or_none()
        
        if not test:
            return None
        
        # Get variations
        stmt = select(ABTestVariation).where(
            ABTestVariation.ab_test_id == ab_test_id
        ).order_by(ABTestVariation.conversion_rate.desc())
        result = await self.session.execute(stmt)
        variations = result.scalars().all()
        
        # Calculate metrics for each variation
        variations_data = []
        for variation in variations:
            confidence_interval = self._calculate_wilson_score(
                variation.conversions,
                variation.times_sent
            )
            
            variations_data.append({
                "id": str(variation.id),
                "subject_line": variation.subject_line,
                "times_selected": variation.times_selected,
                "times_sent": variation.times_sent,
                "opens": variation.opens,
                "clicks": variation.clicks,
                "conversions": variation.conversions,
                "open_rate": variation.open_rate,
                "click_rate": variation.click_rate,
                "conversion_rate": variation.conversion_rate,
                "confidence_interval": confidence_interval
            })
        
        return {
            "test_id": str(ab_test_id),
            "test_name": test.name,
            "status": test.status,
            "created_at": test.created_at.isoformat(),
            "total_samples": sum(v.times_sent for v in variations),
            "variations": variations_data
        }