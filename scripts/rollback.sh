#!/bin/bash

# Email Subject Line Optimizer - Rollback Script
# Usage: ./rollback.sh [version]
# Example: ./rollback.sh v1.0.0

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Default values
ROLLBACK_VERSION=${1:-}
REGISTRY=${REGISTRY:-ghcr.io}
IMAGE_NAME=${IMAGE_NAME:-email-optimizer}

# Function to print colored output
print_message() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# Function to get last deployed version
get_last_deployed_version() {
    if [ -f "$PROJECT_ROOT/.last_deployed_version" ]; then
        LAST_VERSION=$(cat "$PROJECT_ROOT/.last_deployed_version")
        print_message "$GREEN" "Last deployed version: $LAST_VERSION"
    else
        print_message "$RED" "No previous deployment version found"
        
        # Try to get from Docker
        LAST_VERSION=$(docker images --format "table {{.Repository}}:{{.Tag}}" | grep "$IMAGE_NAME" | head -2 | tail -1 || echo "")
        
        if [ -z "$LAST_VERSION" ]; then
            print_message "$RED" "Unable to determine previous version"
            exit 1
        fi
    fi
}

# Function to verify rollback version exists
verify_rollback_version() {
    local version_to_check="${1:-$LAST_VERSION}"
    
    print_message "$YELLOW" "Verifying rollback version exists..."
    
    # Check if image exists locally
    if docker images | grep -q "$version_to_check"; then
        print_message "$GREEN" "Rollback version found locally"
        return 0
    fi
    
    # Try to pull from registry
    print_message "$YELLOW" "Attempting to pull rollback version from registry..."
    if docker pull "$version_to_check" 2>/dev/null; then
        print_message "$GREEN" "Rollback version pulled from registry"
        return 0
    fi
    
    print_message "$RED" "Rollback version not available"
    return 1
}

# Function to backup current state
backup_current_state() {
    print_message "$YELLOW" "Backing up current state before rollback..."
    
    # Save current container logs
    local log_dir="$PROJECT_ROOT/rollback_logs/${TIMESTAMP}"
    mkdir -p "$log_dir"
    
    docker-compose logs --no-color > "$log_dir/docker_compose.log" 2>&1 || true
    docker ps -a > "$log_dir/docker_ps.txt" 2>&1 || true
    docker images > "$log_dir/docker_images.txt" 2>&1 || true
    
    # Save current version
    CURRENT_VERSION=$(docker ps --format "table {{.Image}}" | grep "$IMAGE_NAME" | head -1 || echo "unknown")
    echo "$CURRENT_VERSION" > "$log_dir/current_version.txt"
    
    print_message "$GREEN" "Current state backed up to: $log_dir"
}

# Function to perform rollback
perform_rollback() {
    local target_version="${1:-$LAST_VERSION}"
    
    print_message "$YELLOW" "Rolling back to version: $target_version"
    
    # Determine environment file
    if [ -f "$PROJECT_ROOT/.env.production" ]; then
        ENV_FILE=".env.production"
    else
        ENV_FILE=".env"
    fi
    
    cd "$PROJECT_ROOT"
    
    # Export the target version for docker-compose
    export IMAGE_TAG="$target_version"
    
    # Stop current containers
    print_message "$YELLOW" "Stopping current containers..."
    docker-compose --env-file "$ENV_FILE" stop app
    
    # Remove current containers
    print_message "$YELLOW" "Removing current containers..."
    docker-compose --env-file "$ENV_FILE" rm -f app
    
    # Start with rollback version
    print_message "$YELLOW" "Starting rollback version..."
    docker-compose --env-file "$ENV_FILE" up -d app
    
    print_message "$GREEN" "Rollback deployment completed"
}

# Function to verify rollback
verify_rollback() {
    print_message "$YELLOW" "Verifying rollback..."
    
    # Wait for services to be ready
    sleep 10
    
    # Check health endpoint
    local max_attempts=10
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if curl -f http://localhost:8000/health &> /dev/null; then
            print_message "$GREEN" "Health check passed"
            break
        else
            if [ $attempt -eq $max_attempts ]; then
                print_message "$RED" "Health check failed after rollback"
                
                # Show logs
                docker-compose logs --tail=50 app
                
                return 1
            else
                print_message "$YELLOW" "Health check attempt $attempt failed, retrying..."
                sleep 5
                attempt=$((attempt + 1))
            fi
        fi
    done
    
    # Verify application is running correct version
    local running_version=$(docker ps --format "table {{.Image}}" | grep "$IMAGE_NAME" | head -1)
    print_message "$GREEN" "Running version after rollback: $running_version"
    
    return 0
}

# Function to restore database if needed
restore_database() {
    local restore_db="${RESTORE_DATABASE:-false}"
    
    if [ "$restore_db" == "true" ]; then
        print_message "$YELLOW" "Restoring database from backup..."
        
        # Find most recent backup
        local latest_backup=$(ls -t "$PROJECT_ROOT/backups/"*_postgres.sql.gz 2>/dev/null | head -1)
        
        if [ -f "$latest_backup" ]; then
            print_message "$YELLOW" "Found backup: $latest_backup"
            
            # Restore database
            if docker ps | grep -q "email-optimizer-postgres"; then
                gunzip -c "$latest_backup" | docker exec -i email-optimizer-postgres psql -U postgres -d email_optimizer
                print_message "$GREEN" "Database restored from backup"
            else
                print_message "$RED" "PostgreSQL container not found"
            fi
        else
            print_message "$YELLOW" "No database backup found, skipping restore"
        fi
    fi
}

# Function to cleanup after rollback
cleanup_after_rollback() {
    print_message "$YELLOW" "Cleaning up after rollback..."
    
    # Remove failed version image (optional)
    if [ ! -z "$CURRENT_VERSION" ] && [ "$CURRENT_VERSION" != "unknown" ]; then
        read -p "Remove failed version image ($CURRENT_VERSION)? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            docker rmi "$CURRENT_VERSION" 2>/dev/null || true
            print_message "$GREEN" "Removed failed version image"
        fi
    fi
    
    # Clean up dangling images
    docker image prune -f
    
    print_message "$GREEN" "Cleanup completed"
}

# Function to send notification
send_notification() {
    local status=$1
    local message=$2
    
    # Send Slack notification if webhook is configured
    if [ ! -z "$SLACK_WEBHOOK" ]; then
        curl -X POST -H 'Content-type: application/json' \
            --data "{\"text\":\"Rollback ${status}: ${message}\"}" \
            "$SLACK_WEBHOOK" 2>/dev/null || true
    fi
    
    # Log rollback
    echo "[$TIMESTAMP] Rollback $status: $message" >> "$PROJECT_ROOT/rollbacks.log"
}

# Main rollback process
main() {
    print_message "$RED" "========================================="
    print_message "$RED" "Email Optimizer Rollback"
    print_message "$RED" "Timestamp: $TIMESTAMP"
    print_message "$RED" "========================================="
    
    # Determine rollback version
    if [ -z "$ROLLBACK_VERSION" ]; then
        get_last_deployed_version
        ROLLBACK_VERSION="$LAST_VERSION"
    fi
    
    # Verify rollback version exists
    if ! verify_rollback_version "$ROLLBACK_VERSION"; then
        print_message "$RED" "Cannot proceed with rollback - version not available"
        exit 1
    fi
    
    # Backup current state
    backup_current_state
    
    # Perform rollback
    perform_rollback "$ROLLBACK_VERSION"
    
    # Restore database if needed
    restore_database
    
    # Verify rollback was successful
    if verify_rollback; then
        # Update last deployed version
        echo "$ROLLBACK_VERSION" > "$PROJECT_ROOT/.last_deployed_version"
        
        # Cleanup
        cleanup_after_rollback
        
        # Send success notification
        send_notification "SUCCESS" "Rolled back to version $ROLLBACK_VERSION"
        
        print_message "$GREEN" "========================================="
        print_message "$GREEN" "Rollback completed successfully!"
        print_message "$GREEN" "Rolled back to: $ROLLBACK_VERSION"
        print_message "$GREEN" "========================================="
    else
        # Send failure notification
        send_notification "FAILED" "Rollback to version $ROLLBACK_VERSION failed"
        
        print_message "$RED" "========================================="
        print_message "$RED" "Rollback failed!"
        print_message "$RED" "Manual intervention may be required"
        print_message "$RED" "========================================="
        exit 1
    fi
}

# Error handling
trap 'handle_error $? $LINENO' ERR

handle_error() {
    local exit_code=$1
    local line_number=$2
    
    print_message "$RED" "Rollback script failed at line $line_number with exit code $exit_code"
    send_notification "ERROR" "Rollback script failed at line $line_number"
    
    exit $exit_code
}

# Confirmation prompt
if [ -z "$FORCE_ROLLBACK" ]; then
    print_message "$YELLOW" "This will rollback the application to a previous version."
    read -p "Are you sure you want to continue? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_message "$YELLOW" "Rollback cancelled"
        exit 0
    fi
fi

# Run main function
main