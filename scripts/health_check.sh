#!/bin/bash

# Email Subject Line Optimizer - Health Check Script
# Usage: ./health_check.sh [environment]
# Example: ./health_check.sh production

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Default values
ENVIRONMENT=${1:-local}
BASE_URL=${BASE_URL:-http://localhost:8000}

# Override base URL for different environments
case "$ENVIRONMENT" in
    production)
        BASE_URL=${PROD_URL:-https://email-optimizer.example.com}
        ;;
    staging)
        BASE_URL=${STAGING_URL:-https://staging.email-optimizer.example.com}
        ;;
    local)
        BASE_URL="http://localhost:8000"
        ;;
esac

# Health check results
TOTAL_CHECKS=0
PASSED_CHECKS=0
FAILED_CHECKS=0
WARNINGS=0

# Function to print colored output
print_message() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# Function to check endpoint
check_endpoint() {
    local endpoint=$1
    local expected_status=${2:-200}
    local description=$3
    
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    
    print_message "$BLUE" "Checking: $description"
    
    local response=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL$endpoint" 2>/dev/null || echo "000")
    
    if [ "$response" == "$expected_status" ]; then
        print_message "$GREEN" "  ✓ $description - Status: $response"
        PASSED_CHECKS=$((PASSED_CHECKS + 1))
        return 0
    else
        print_message "$RED" "  ✗ $description - Expected: $expected_status, Got: $response"
        FAILED_CHECKS=$((FAILED_CHECKS + 1))
        return 1
    fi
}

# Function to check endpoint with data
check_endpoint_with_data() {
    local endpoint=$1
    local method=$2
    local data=$3
    local expected_status=$4
    local description=$5
    
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    
    print_message "$BLUE" "Checking: $description"
    
    local response=$(curl -s -o /dev/null -w "%{http_code}" \
        -X "$method" \
        -H "Content-Type: application/json" \
        -d "$data" \
        "$BASE_URL$endpoint" 2>/dev/null || echo "000")
    
    if [ "$response" == "$expected_status" ]; then
        print_message "$GREEN" "  ✓ $description - Status: $response"
        PASSED_CHECKS=$((PASSED_CHECKS + 1))
        return 0
    else
        print_message "$RED" "  ✗ $description - Expected: $expected_status, Got: $response"
        FAILED_CHECKS=$((FAILED_CHECKS + 1))
        return 1
    fi
}

# Function to check service health
check_service_health() {
    local service=$1
    local container_name=$2
    
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    
    print_message "$BLUE" "Checking: $service service"
    
    if [ "$ENVIRONMENT" == "local" ]; then
        if docker ps | grep -q "$container_name"; then
            local status=$(docker inspect -f '{{.State.Health.Status}}' "$container_name" 2>/dev/null || echo "none")
            
            if [ "$status" == "healthy" ]; then
                print_message "$GREEN" "  ✓ $service is healthy"
                PASSED_CHECKS=$((PASSED_CHECKS + 1))
            elif [ "$status" == "none" ]; then
                print_message "$YELLOW" "  ⚠ $service has no health check"
                WARNINGS=$((WARNINGS + 1))
                PASSED_CHECKS=$((PASSED_CHECKS + 1))
            else
                print_message "$RED" "  ✗ $service status: $status"
                FAILED_CHECKS=$((FAILED_CHECKS + 1))
            fi
        else
            print_message "$RED" "  ✗ $service container not running"
            FAILED_CHECKS=$((FAILED_CHECKS + 1))
        fi
    else
        print_message "$YELLOW" "  ⚠ Cannot check $service remotely"
        WARNINGS=$((WARNINGS + 1))
    fi
}

# Function to check database connectivity
check_database() {
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    
    print_message "$BLUE" "Checking: Database connectivity"
    
    if [ "$ENVIRONMENT" == "local" ]; then
        if docker exec email-optimizer-postgres pg_isready -U postgres &>/dev/null; then
            print_message "$GREEN" "  ✓ Database is ready"
            PASSED_CHECKS=$((PASSED_CHECKS + 1))
            
            # Check table existence
            local tables=$(docker exec email-optimizer-postgres psql -U postgres -d email_optimizer -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';" 2>/dev/null || echo "0")
            tables=$(echo $tables | tr -d ' ')
            
            if [ "$tables" -gt "0" ]; then
                print_message "$GREEN" "  ✓ Database has $tables tables"
            else
                print_message "$YELLOW" "  ⚠ Database has no tables"
                WARNINGS=$((WARNINGS + 1))
            fi
        else
            print_message "$RED" "  ✗ Database is not ready"
            FAILED_CHECKS=$((FAILED_CHECKS + 1))
        fi
    else
        # For remote environments, check via health endpoint
        local health_response=$(curl -s "$BASE_URL/health" 2>/dev/null || echo "{}")
        if echo "$health_response" | grep -q "database.*healthy"; then
            print_message "$GREEN" "  ✓ Database is healthy (via health endpoint)"
            PASSED_CHECKS=$((PASSED_CHECKS + 1))
        else
            print_message "$YELLOW" "  ⚠ Cannot verify database remotely"
            WARNINGS=$((WARNINGS + 1))
        fi
    fi
}

# Function to check Redis connectivity
check_redis() {
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    
    print_message "$BLUE" "Checking: Redis connectivity"
    
    if [ "$ENVIRONMENT" == "local" ]; then
        if docker exec email-optimizer-redis redis-cli ping &>/dev/null; then
            print_message "$GREEN" "  ✓ Redis is responding"
            PASSED_CHECKS=$((PASSED_CHECKS + 1))
            
            # Check Redis memory usage
            local memory=$(docker exec email-optimizer-redis redis-cli INFO memory | grep used_memory_human | cut -d: -f2 | tr -d '\r')
            print_message "$GREEN" "  ✓ Redis memory usage: $memory"
        else
            print_message "$RED" "  ✗ Redis is not responding"
            FAILED_CHECKS=$((FAILED_CHECKS + 1))
        fi
    else
        # For remote environments, check via health endpoint
        local health_response=$(curl -s "$BASE_URL/health" 2>/dev/null || echo "{}")
        if echo "$health_response" | grep -q "redis.*healthy"; then
            print_message "$GREEN" "  ✓ Redis is healthy (via health endpoint)"
            PASSED_CHECKS=$((PASSED_CHECKS + 1))
        else
            print_message "$YELLOW" "  ⚠ Cannot verify Redis remotely"
            WARNINGS=$((WARNINGS + 1))
        fi
    fi
}

# Function to check API functionality
check_api_functionality() {
    print_message "$YELLOW" "\n=== API Functionality Checks ==="
    
    # Test subject generation endpoint
    local test_data='{"email_body": "Join us for our annual conference featuring keynote speakers, networking opportunities, and hands-on workshops.", "tone": "professional"}'
    
    check_endpoint_with_data "/api/v1/generate" "POST" "$test_data" "200" "Subject generation API"
    
    # Test analytics endpoint
    check_endpoint "/api/v1/analytics/subjects" "200" "Analytics API"
    
    # Test A/B test endpoint
    check_endpoint "/api/v1/ab-tests" "200" "A/B Tests API"
}

# Function to check metrics
check_metrics() {
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    
    print_message "$BLUE" "Checking: Prometheus metrics"
    
    local metrics_response=$(curl -s "$BASE_URL/metrics" 2>/dev/null || echo "")
    
    if echo "$metrics_response" | grep -q "email_optimizer_"; then
        print_message "$GREEN" "  ✓ Metrics endpoint is working"
        PASSED_CHECKS=$((PASSED_CHECKS + 1))
        
        # Check for specific metrics
        local metrics=("http_requests_total" "ai_requests_total" "cache_operations_total")
        for metric in "${metrics[@]}"; do
            if echo "$metrics_response" | grep -q "email_optimizer_$metric"; then
                print_message "$GREEN" "    ✓ Metric: email_optimizer_$metric"
            else
                print_message "$YELLOW" "    ⚠ Missing metric: email_optimizer_$metric"
                WARNINGS=$((WARNINGS + 1))
            fi
        done
    else
        print_message "$RED" "  ✗ Metrics endpoint not working"
        FAILED_CHECKS=$((FAILED_CHECKS + 1))
    fi
}

# Function to check logs
check_logs() {
    if [ "$ENVIRONMENT" == "local" ]; then
        print_message "$YELLOW" "\n=== Recent Logs Check ==="
        
        # Check for errors in logs
        local error_count=$(docker-compose logs --tail=100 2>/dev/null | grep -c ERROR || echo "0")
        
        if [ "$error_count" -eq "0" ]; then
            print_message "$GREEN" "  ✓ No errors in recent logs"
        else
            print_message "$YELLOW" "  ⚠ Found $error_count error(s) in recent logs"
            WARNINGS=$((WARNINGS + 1))
        fi
        
        # Check for warnings
        local warning_count=$(docker-compose logs --tail=100 2>/dev/null | grep -c WARNING || echo "0")
        if [ "$warning_count" -gt "0" ]; then
            print_message "$YELLOW" "  ⚠ Found $warning_count warning(s) in recent logs"
        fi
    fi
}

# Function to generate health report
generate_health_report() {
    local report_file="$PROJECT_ROOT/health_report_${TIMESTAMP}.json"
    
    cat > "$report_file" << EOF
{
    "timestamp": "$TIMESTAMP",
    "environment": "$ENVIRONMENT",
    "base_url": "$BASE_URL",
    "checks": {
        "total": $TOTAL_CHECKS,
        "passed": $PASSED_CHECKS,
        "failed": $FAILED_CHECKS,
        "warnings": $WARNINGS
    },
    "status": "$([ $FAILED_CHECKS -eq 0 ] && echo "healthy" || echo "unhealthy")",
    "score": $(echo "scale=2; $PASSED_CHECKS * 100 / $TOTAL_CHECKS" | bc)
}
EOF
    
    print_message "$BLUE" "\nHealth report saved to: $report_file"
}

# Main health check process
main() {
    print_message "$GREEN" "========================================="
    print_message "$GREEN" "Email Optimizer Health Check"
    print_message "$GREEN" "Environment: $ENVIRONMENT"
    print_message "$GREEN" "Base URL: $BASE_URL"
    print_message "$GREEN" "Timestamp: $TIMESTAMP"
    print_message "$GREEN" "========================================="
    
    # Basic connectivity checks
    print_message "$YELLOW" "\n=== Basic Connectivity Checks ==="
    check_endpoint "/" "200" "Root endpoint"
    check_endpoint "/health" "200" "Health endpoint"
    check_endpoint "/docs" "200" "API documentation"
    check_endpoint "/metrics" "200" "Metrics endpoint"
    
    # Service checks
    print_message "$YELLOW" "\n=== Service Health Checks ==="
    if [ "$ENVIRONMENT" == "local" ]; then
        check_service_health "Application" "email-optimizer-app"
        check_service_health "PostgreSQL" "email-optimizer-postgres"
        check_service_health "Redis" "email-optimizer-redis"
    fi
    
    # Database and Redis checks
    check_database
    check_redis
    
    # API functionality checks
    check_api_functionality
    
    # Metrics check
    print_message "$YELLOW" "\n=== Monitoring Checks ==="
    check_metrics
    
    # Logs check
    check_logs
    
    # Generate report
    generate_health_report
    
    # Summary
    print_message "$GREEN" "\n========================================="
    print_message "$GREEN" "Health Check Summary"
    print_message "$GREEN" "========================================="
    print_message "$BLUE" "Total Checks: $TOTAL_CHECKS"
    print_message "$GREEN" "Passed: $PASSED_CHECKS"
    print_message "$RED" "Failed: $FAILED_CHECKS"
    print_message "$YELLOW" "Warnings: $WARNINGS"
    
    local score=$(echo "scale=2; $PASSED_CHECKS * 100 / $TOTAL_CHECKS" | bc)
    print_message "$BLUE" "Health Score: ${score}%"
    
    if [ $FAILED_CHECKS -eq 0 ]; then
        print_message "$GREEN" "Status: HEALTHY ✓"
        print_message "$GREEN" "========================================="
        exit 0
    else
        print_message "$RED" "Status: UNHEALTHY ✗"
        print_message "$RED" "========================================="
        exit 1
    fi
}

# Run main function
main