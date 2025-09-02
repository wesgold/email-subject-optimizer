"""Complete test of Phase 4 functionality."""

import asyncio
import uuid
from src.config.database import AsyncSessionLocal
from src.models.ab_testing import ABTest, ABTestVariation, ABTestEvent
from src.services.ab_testing import MultiArmedBanditService
from src.services.analytics import AnalyticsService
import random

async def create_test_data():
    """Create test data with UUIDs."""
    async with AsyncSessionLocal() as session:
        # Create an A/B test
        test_id = uuid.uuid4()
        ab_test = ABTest(
            id=test_id,
            email_content_hash="test_hash_phase4",
            original_subject="Phase 4 Test Email",
            name="Phase 4 Multi-Armed Bandit Test",
            status="active"
        )
        session.add(ab_test)
        
        # Create 5 variations
        variations = []
        subject_lines = [
            "[!] Limited Time: 50% Off Everything!",
            "Act Now: Exclusive Deals Inside",
            "Your Special Discount Awaits",
            "Flash Sale: Save Big Today Only",
            "VIP Access: Premium Offers for You"
        ]
        
        for i, subject in enumerate(subject_lines):
            var = ABTestVariation(
                id=uuid.uuid4(),
                ab_test_id=test_id,
                subject_line=subject,
                variation_index=i
            )
            session.add(var)
            variations.append(var)
        
        await session.commit()
        print(f"[OK] Created A/B test: {test_id}")
        print(f"[OK] Created {len(variations)} variations")
        
        return test_id, [v.id for v in variations]

async def simulate_events(test_id, variation_ids):
    """Simulate events with different performance levels."""
    async with AsyncSessionLocal() as session:
        bandit_service = MultiArmedBanditService(session)
        
        # Define performance profiles (open rate, click rate, conversion rate)
        performance = [
            (0.35, 0.15, 0.08),  # Best performer
            (0.25, 0.10, 0.05),  # Good
            (0.20, 0.08, 0.03),  # Average
            (0.15, 0.05, 0.02),  # Below average
            (0.10, 0.03, 0.01),  # Poor
        ]
        
        print("\n[STATS] Simulating events...")
        
        # Simulate sends distributed based on exploration
        for round in range(10):
            for i, var_id in enumerate(variation_ids):
                # Number of sends based on performance
                sends = 10 if round < 2 else random.randint(5, 15)
                
                for _ in range(sends):
                    # Record send
                    await bandit_service.record_event(var_id, "send")
                    
                    # Simulate opens based on performance
                    if random.random() < performance[i][0]:
                        await bandit_service.record_event(var_id, "open")
                        
                        # Simulate clicks
                        if random.random() < (performance[i][1] / performance[i][0]):
                            await bandit_service.record_event(var_id, "click")
                            
                            # Simulate conversions
                            if random.random() < (performance[i][2] / performance[i][1]):
                                await bandit_service.record_event(var_id, "conversion")
        
        print("[OK] Events simulated")

async def test_bandit_selection(test_id):
    """Test multi-armed bandit selection."""
    async with AsyncSessionLocal() as session:
        bandit_service = MultiArmedBanditService(session)
        
        print("\n[BANDIT] Testing Multi-Armed Bandit Selection:")
        
        # Test selection multiple times
        selections = {}
        for _ in range(20):
            result = await bandit_service.select_variation(test_id)
            if result:
                var_id = result["id"]
                selections[var_id] = selections.get(var_id, 0) + 1
        
        print("\nSelection distribution (20 selections):")
        for var_id, count in sorted(selections.items(), key=lambda x: x[1], reverse=True):
            print(f"  Variation {var_id[:8]}...: {count} selections")
        
        # Get detailed performance
        perf = await bandit_service.get_test_performance(test_id)
        if perf:
            print("\n[PERF] Performance Summary:")
            for var in perf["variations"]:
                print(f"\n  {var['subject_line'][:40]}...")
                print(f"    Conversion rate: {var['conversion_rate']:.2%}")
                print(f"    Confidence interval: [{var['confidence_interval']['lower']:.2%}, {var['confidence_interval']['upper']:.2%}]")
                print(f"    Times selected: {var['times_selected']}")

async def test_analytics(test_id):
    """Test analytics service."""
    async with AsyncSessionLocal() as session:
        analytics_service = AnalyticsService(session)
        
        print("\n[STATS] Testing Analytics Service:")
        
        # Get dashboard metrics
        dashboard = await analytics_service.get_dashboard_metrics()
        print(f"\n  Total tests: {dashboard['tests']['total']}")
        print(f"  Active tests: {dashboard['tests']['active']}")
        print(f"  Overall conversion rate: {dashboard['overall_metrics']['conversion_rate']:.2%}")
        
        # Get top performers
        top = await analytics_service.get_top_performing_subjects(limit=3, min_sends=10)
        if top:
            print("\n  Top Performing Subject Lines:")
            for i, subject in enumerate(top, 1):
                print(f"    {i}. {subject['subject_line'][:50]}...")
                print(f"       Conversion: {subject['metrics']['conversion_rate']:.2%}")
        
        # Get test comparison
        comparison = await analytics_service.get_test_comparison(test_id)
        if comparison and comparison.get("winner"):
            print(f"\n  [WINNER] Winner: {comparison['winner']['subject_line'][:50]}...")
            print(f"     Improvement: {comparison['winner']['improvement']:.1f}%")

async def main():
    """Run complete Phase 4 test."""
    print("=" * 60)
    print("PHASE 4: Multi-Armed Bandit A/B Testing")
    print("=" * 60)
    
    # Create test data
    test_id, variation_ids = await create_test_data()
    
    # Simulate events
    await simulate_events(test_id, variation_ids)
    
    # Test bandit selection
    await test_bandit_selection(test_id)
    
    # Test analytics
    await test_analytics(test_id)
    
    print("\n" + "=" * 60)
    print("[OK] PHASE 4 TESTING COMPLETE!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())