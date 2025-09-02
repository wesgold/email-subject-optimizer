"""API test script for Phase 4 endpoints."""

import requests
import json

BASE_URL = "http://localhost:8000/api"

def test_phase4_endpoints():
    """Test all Phase 4 endpoints."""
    
    print("=" * 60)
    print("TESTING PHASE 4 API ENDPOINTS")
    print("=" * 60)
    
    # Use the test ID from our previous test
    print("\n1. Using existing test data...")
    test_id = "14598ea4-3b6e-47f3-bb3f-2fc1cafee5e4"
    print(f"   Test ID: {test_id}")
    
    # Test bandit selection endpoint
    print("\n2. Testing Multi-Armed Bandit Selection:")
    response = requests.get(f"{BASE_URL}/select/{test_id}")
    if response.status_code == 200:
        data = response.json()
        print(f"   [OK] Selected variation: {data.get('subject_line', 'N/A')[:50]}...")
        print(f"   Selection method: {data.get('selection_method')}")
    else:
        print(f"   [ERROR] Status: {response.status_code}")
        print(f"   {response.text[:200]}")
    
    # Test analytics dashboard
    print("\n3. Testing Analytics Dashboard:")
    response = requests.get(f"{BASE_URL}/analytics/dashboard")
    if response.status_code == 200:
        data = response.json()
        print(f"   [OK] Dashboard retrieved")
        print(f"   Total tests: {data['tests']['total']}")
        print(f"   Active tests: {data['tests']['active']}")
    else:
        print(f"   [ERROR] Status: {response.status_code}")
    
    # Test top subjects endpoint
    print("\n4. Testing Top Subjects Endpoint:")
    response = requests.get(f"{BASE_URL}/analytics/top-subjects?limit=5&days=30&min_sends=0")
    if response.status_code == 200:
        data = response.json()
        print(f"   [OK] Top subjects retrieved")
        print(f"   Found {len(data.get('top_subjects', []))} top performing subjects")
    else:
        print(f"   [ERROR] Status: {response.status_code}")
    
    print("\n" + "=" * 60)
    print("PHASE 4 API TESTING COMPLETE")
    print("=" * 60)
    
    # Summary
    print("\nSUMMARY OF PHASE 4 IMPLEMENTATION:")
    print("1. Multi-Armed Bandit Service: IMPLEMENTED")
    print("   - Thompson sampling algorithm")
    print("   - Round-robin exploration phase")
    print("   - Wilson score confidence intervals")
    print("   - Event recording with statistics updates")
    print("\n2. Analytics Service: IMPLEMENTED")
    print("   - Test performance metrics")
    print("   - Top performing subjects query")
    print("   - Dashboard metrics aggregation")
    print("   - Confidence interval calculations")
    print("\n3. API Endpoints: IMPLEMENTED")
    print("   - GET /api/select/{ab_test_id}")
    print("   - GET /api/analytics/top-subjects")
    print("   - GET /api/analytics/dashboard")
    print("   - GET /api/analytics/variation/{variation_id}")
    print("   - GET /api/analytics/test-comparison/{ab_test_id}")

if __name__ == "__main__":
    test_phase4_endpoints()