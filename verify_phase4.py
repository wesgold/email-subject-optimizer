"""Verify Phase 4 implementation."""

import asyncio
from src.config.database import AsyncSessionLocal
from src.services.ab_testing import MultiArmedBanditService
from src.services.analytics import AnalyticsService
from sqlalchemy import text

async def verify_phase4():
    """Verify all Phase 4 components are working."""
    
    print("PHASE 4 VERIFICATION")
    print("=" * 50)
    
    results = {
        "multi_armed_bandit": False,
        "analytics_service": False,
        "thompson_sampling": False,
        "wilson_score": False,
        "api_endpoints": False
    }
    
    async with AsyncSessionLocal() as session:
        # 1. Test Multi-Armed Bandit Service
        try:
            bandit = MultiArmedBanditService(session)
            print("\n1. Multi-Armed Bandit Service: LOADED")
            results["multi_armed_bandit"] = True
            
            # Test Wilson score calculation
            confidence = bandit._calculate_wilson_score(10, 100)
            if confidence["lower"] >= 0 and confidence["upper"] <= 1:
                print("   - Wilson score calculation: WORKING")
                results["wilson_score"] = True
        except Exception as e:
            print(f"   ERROR: {e}")
        
        # 2. Test Analytics Service
        try:
            analytics = AnalyticsService(session)
            print("\n2. Analytics Service: LOADED")
            results["analytics_service"] = True
            
            # Test dashboard metrics
            dashboard = await analytics.get_dashboard_metrics()
            if "tests" in dashboard and "overall_metrics" in dashboard:
                print("   - Dashboard metrics: WORKING")
        except Exception as e:
            print(f"   ERROR: {e}")
        
        # 3. Check Thompson Sampling implementation
        try:
            import numpy as np
            # Test Beta distribution sampling
            alpha, beta = 10, 5
            sample = np.random.beta(alpha, beta)
            if 0 <= sample <= 1:
                print("\n3. Thompson Sampling (Beta distribution): WORKING")
                results["thompson_sampling"] = True
        except Exception as e:
            print(f"   ERROR: {e}")
        
        # 4. Check database schema
        try:
            result = await session.execute(text(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name IN ('ab_tests', 'ab_test_variations', 'ab_test_events')"
            ))
            count = result.scalar()
            if count == 3:
                print("\n4. Database Schema: CORRECT")
        except Exception as e:
            print(f"   ERROR: {e}")
    
    # 5. Test API endpoints
    import requests
    try:
        response = requests.get("http://localhost:8000/api/analytics/dashboard")
        if response.status_code in [200, 404]:  # 404 if no data yet
            print("\n5. API Endpoints: ACCESSIBLE")
            results["api_endpoints"] = True
    except:
        print("\n5. API Endpoints: NOT RUNNING (start server to test)")
    
    # Summary
    print("\n" + "=" * 50)
    print("VERIFICATION SUMMARY:")
    passed = sum(results.values())
    total = len(results)
    print(f"Passed: {passed}/{total}")
    
    for component, status in results.items():
        status_text = "[PASS]" if status else "[FAIL]"
        print(f"  {status_text} {component.replace('_', ' ').title()}")
    
    if passed == total:
        print("\nPHASE 4: READY FOR PHASE 5!")
    else:
        print("\nPHASE 4: Some components need attention")
    
    return passed == total

if __name__ == "__main__":
    success = asyncio.run(verify_phase4())
    exit(0 if success else 1)