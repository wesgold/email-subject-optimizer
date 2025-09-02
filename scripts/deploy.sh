#!/bin/bash

# Email Subject Line Optimizer - Deployment Script
# Usage: ./deploy.sh [environment] [version]
# Example: ./deploy.sh production v1.0.0

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
ENVIRONMENT=${1:-staging}
VERSION=${2:-latest}
REGISTRY=${REGISTRY:-ghcr.io}
IMAGE_NAME=${IMAGE_NAME:-email-optimizer}
BACKUP_BEFORE_DEPLOY=${BACKUP_BEFORE_DEPLOY:-true}

# Function to print colored output
print_message() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# Function to check prerequisites
check_prerequisites() {
    print_message "$YELLOW" "Checking prerequisites..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        print_message "$RED" "Docker is not installed"
        exit 1
    fi
    
    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        print_message "$RED" "Docker Compose is not installed"
        exit 1
    fi
    
    # Check environment file
    if [ "$ENVIRONMENT" == "production" ]; then
        if [ ! -f "$PROJECT_ROOT/.env.production" ]; then
            print_message "$RED" ".env.production file not found"
            exit 1
        fi
        ENV_FILE=".env.production"
    elif [ "$ENVIRONMENT" == "staging" ]; then
        if [ ! -f "$PROJECT_ROOT/.env.staging" ]; then
            print_message "$YELLOW" ".env.staging not found, using .env"
            ENV_FILE=".env"
        else
            ENV_FILE=".env.staging"
        fi
    else
        ENV_FILE=".env"
    fi
    
    print_message "$GREEN" "Prerequisites check passed"
}

# Function to backup database
backup_database() {
    if [ "$BACKUP_BEFORE_DEPLOY" == "true" ] && [ "$ENVIRONMENT" == "production" ]; then
        print_message "$YELLOW" "Creating database backup..."
        
        # Run backup script
        if [ -f "$SCRIPT_DIR/backup.sh" ]; then
            "$SCRIPT_DIR/backup.sh"
        else
            print_message "$YELLOW" "Backup script not found, skipping backup"
        fi
    fi
}

# Function to pull latest images
pull_images() {
    print_message "$YELLOW" "Pulling latest images..."
    
    cd "$PROJECT_ROOT"
    
    # Pull specific version or latest
    if [ "$VERSION" != "latest" ]; then
        export IMAGE_TAG="${REGISTRY}/${IMAGE_NAME}:${VERSION}"
    else
        export IMAGE_TAG="${REGISTRY}/${IMAGE_NAME}:latest"
    fi
    
    docker-compose --env-file "$ENV_FILE" pull
    
    print_message "$GREEN" "Images pulled successfully"
}

# Function to run database migrations
run_migrations() {
    print_message "$YELLOW" "Running database migrations..."
    
    cd "$PROJECT_ROOT"
    
    # Run migrations in a temporary container
    docker-compose --env-file "$ENV_FILE" run --rm app alembic upgrade head
    
    print_message "$GREEN" "Migrations completed successfully"
}

# Function to deploy application
deploy_application() {
    print_message "$YELLOW" "Deploying application..."
    
    cd "$PROJECT_ROOT"
    
    # Store current version for potential rollback
    CURRENT_VERSION=$(docker ps --format "table {{.Image}}" | grep "$IMAGE_NAME" | head -1 || echo "none")
    echo "$CURRENT_VERSION" > "$PROJECT_ROOT/.last_deployed_version"
    
    # Deploy based on environment
    if [ "$ENVIRONMENT" == "production" ]; then
        # Production: Rolling deployment with zero downtime
        print_message "$YELLOW" "Performing rolling deployment..."
        
        # Scale up
        docker-compose --env-file "$ENV_FILE" up -d --no-deps --scale app=2 app
        
        # Wait for new containers to be healthy
        sleep 30
        
        # Check health
        if ! docker-compose --env-file "$ENV_FILE" exec -T app curl -f http://localhost:8000/health; then
            print_message "$RED" "Health check failed, rolling back..."
            "$SCRIPT_DIR/rollback.sh"
            exit 1
        fi
        
        # Scale down to normal
        docker-compose --env-file "$ENV_FILE" up -d --no-deps --remove-orphans app
        
    else
        # Non-production: Simple deployment
        docker-compose --env-file "$ENV_FILE" up -d --remove-orphans
    fi
    
    print_message "$GREEN" "Application deployed successfully"
}

# Function to verify deployment
verify_deployment() {
    print_message "$YELLOW" "Verifying deployment..."
    
    # Wait for services to be ready
    sleep 10
    
    # Check health endpoint
    if command -v curl &> /dev/null; then
        HEALTH_CHECK_URL="http://localhost:8000/health"
        
        for i in {1..10}; do
            if curl -f "$HEALTH_CHECK_URL" &> /dev/null; then
                print_message "$GREEN" "Health check passed"
                break
            else
                if [ $i -eq 10 ]; then
                    print_message "$RED" "Health check failed after 10 attempts"
                    
                    # Show logs for debugging
                    docker-compose --env-file "$ENV_FILE" logs --tail=50 app
                    
                    if [ "$ENVIRONMENT" == "production" ]; then
                        print_message "$YELLOW" "Rolling back deployment..."
                        "$SCRIPT_DIR/rollback.sh"
                        exit 1
                    fi
                else
                    print_message "$YELLOW" "Health check attempt $i failed, retrying..."
                    sleep 5
                fi
            fi
        done
    fi
    
    # Show running containers
    print_message "$YELLOW" "Running containers:"
    docker-compose --env-file "$ENV_FILE" ps
}

# Function to cleanup old images
cleanup_old_images() {
    print_message "$YELLOW" "Cleaning up old images..."
    
    # Remove unused images
    docker image prune -f
    
    # Remove images older than 7 days (keep recent ones for rollback)
    docker images | grep "$IMAGE_NAME" | grep -E "[0-9]+ days ago" | awk '{print $3}' | xargs -r docker rmi -f 2>/dev/null || true
    
    print_message "$GREEN" "Cleanup completed"
}

# Function to send notification
send_notification() {
    local status=$1
    local message=$2
    
    # Send Slack notification if webhook is configured
    if [ ! -z "$SLACK_WEBHOOK" ]; then
        curl -X POST -H 'Content-type: application/json' \
            --data "{\"text\":\"Deployment ${status}: ${message}\"}" \
            "$SLACK_WEBHOOK" 2>/dev/null || true
    fi
    
    # Log deployment
    echo "[$TIMESTAMP] $ENVIRONMENT deployment $status: $message" >> "$PROJECT_ROOT/deployments.log"
}

# Main deployment process
main() {
    print_message "$GREEN" "========================================="
    print_message "$GREEN" "Email Optimizer Deployment"
    print_message "$GREEN" "Environment: $ENVIRONMENT"
    print_message "$GREEN" "Version: $VERSION"
    print_message "$GREEN" "Timestamp: $TIMESTAMP"
    print_message "$GREEN" "========================================="
    
    # Run deployment steps
    check_prerequisites
    backup_database
    pull_images
    run_migrations
    deploy_application
    verify_deployment
    cleanup_old_images
    
    # Send success notification
    send_notification "SUCCESS" "Deployed version $VERSION to $ENVIRONMENT"
    
    print_message "$GREEN" "========================================="
    print_message "$GREEN" "Deployment completed successfully!"
    print_message "$GREEN" "========================================="
}

# Error handling
trap 'handle_error $? $LINENO' ERR

handle_error() {
    local exit_code=$1
    local line_number=$2
    
    print_message "$RED" "Error occurred at line $line_number with exit code $exit_code"
    send_notification "FAILED" "Deployment failed at line $line_number"
    
    if [ "$ENVIRONMENT" == "production" ]; then
        print_message "$YELLOW" "Attempting automatic rollback..."
        "$SCRIPT_DIR/rollback.sh"
    fi
    
    exit $exit_code
}

# Run main function
main