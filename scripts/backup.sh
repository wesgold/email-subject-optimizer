#!/bin/bash

# Email Subject Line Optimizer - Database Backup Script
# Usage: ./backup.sh [backup_name]
# Example: ./backup.sh pre_deployment_backup

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="${BACKUP_DIR:-$PROJECT_ROOT/backups}"
BACKUP_NAME="${1:-backup_${TIMESTAMP}}"
MAX_BACKUPS=${MAX_BACKUPS:-10}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Database configuration (read from environment or .env file)
if [ -f "$PROJECT_ROOT/.env.production" ]; then
    source "$PROJECT_ROOT/.env.production"
elif [ -f "$PROJECT_ROOT/.env" ]; then
    source "$PROJECT_ROOT/.env"
fi

DB_HOST=${POSTGRES_HOST:-localhost}
DB_PORT=${POSTGRES_PORT:-5432}
DB_NAME=${POSTGRES_DB:-email_optimizer}
DB_USER=${POSTGRES_USER:-postgres}
DB_PASSWORD=${POSTGRES_PASSWORD:-password}

# Redis configuration
REDIS_HOST=${REDIS_HOST:-localhost}
REDIS_PORT=${REDIS_PORT:-6379}

# Function to print colored output
print_message() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# Function to create backup directory
create_backup_directory() {
    if [ ! -d "$BACKUP_DIR" ]; then
        print_message "$YELLOW" "Creating backup directory: $BACKUP_DIR"
        mkdir -p "$BACKUP_DIR"
    fi
}

# Function to backup PostgreSQL database
backup_postgres() {
    print_message "$YELLOW" "Backing up PostgreSQL database..."
    
    local backup_file="$BACKUP_DIR/${BACKUP_NAME}_postgres.sql.gz"
    
    # Check if running in Docker
    if docker ps | grep -q "email-optimizer-postgres"; then
        # Backup from Docker container
        docker exec email-optimizer-postgres pg_dump \
            -U "$DB_USER" \
            -d "$DB_NAME" \
            --no-owner \
            --no-acl \
            --clean \
            --if-exists \
            --verbose | gzip > "$backup_file"
    else
        # Direct backup
        PGPASSWORD="$DB_PASSWORD" pg_dump \
            -h "$DB_HOST" \
            -p "$DB_PORT" \
            -U "$DB_USER" \
            -d "$DB_NAME" \
            --no-owner \
            --no-acl \
            --clean \
            --if-exists \
            --verbose | gzip > "$backup_file"
    fi
    
    # Verify backup
    if [ -f "$backup_file" ]; then
        local size=$(du -h "$backup_file" | cut -f1)
        print_message "$GREEN" "PostgreSQL backup created: $backup_file (Size: $size)"
        
        # Test backup integrity
        if gunzip -t "$backup_file" 2>/dev/null; then
            print_message "$GREEN" "Backup integrity verified"
        else
            print_message "$RED" "Backup integrity check failed!"
            exit 1
        fi
    else
        print_message "$RED" "Failed to create PostgreSQL backup"
        exit 1
    fi
}

# Function to backup Redis
backup_redis() {
    print_message "$YELLOW" "Backing up Redis data..."
    
    local backup_file="$BACKUP_DIR/${BACKUP_NAME}_redis.rdb"
    
    # Check if running in Docker
    if docker ps | grep -q "email-optimizer-redis"; then
        # Trigger Redis save
        docker exec email-optimizer-redis redis-cli BGSAVE
        
        # Wait for save to complete
        while [ $(docker exec email-optimizer-redis redis-cli LASTSAVE) -eq $(docker exec email-optimizer-redis redis-cli LASTSAVE) ]; do
            sleep 1
        done
        
        # Copy dump file
        docker cp email-optimizer-redis:/data/dump.rdb "$backup_file"
    else
        # Direct backup
        redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" BGSAVE
        
        # Wait for save to complete
        sleep 5
        
        # Copy dump file (location may vary)
        if [ -f "/var/lib/redis/dump.rdb" ]; then
            cp "/var/lib/redis/dump.rdb" "$backup_file"
        elif [ -f "/data/dump.rdb" ]; then
            cp "/data/dump.rdb" "$backup_file"
        else
            print_message "$YELLOW" "Redis dump file not found, skipping Redis backup"
            return
        fi
    fi
    
    if [ -f "$backup_file" ]; then
        # Compress Redis backup
        gzip "$backup_file"
        backup_file="${backup_file}.gz"
        
        local size=$(du -h "$backup_file" | cut -f1)
        print_message "$GREEN" "Redis backup created: $backup_file (Size: $size)"
    else
        print_message "$YELLOW" "Redis backup skipped or failed"
    fi
}

# Function to backup application data
backup_application_data() {
    print_message "$YELLOW" "Backing up application data..."
    
    local backup_file="$BACKUP_DIR/${BACKUP_NAME}_app_data.tar.gz"
    
    # List of directories to backup
    local dirs_to_backup=""
    
    # Check for data directory
    if [ -d "$PROJECT_ROOT/data" ]; then
        dirs_to_backup="$dirs_to_backup data"
    fi
    
    # Check for logs directory
    if [ -d "$PROJECT_ROOT/logs" ]; then
        dirs_to_backup="$dirs_to_backup logs"
    fi
    
    # Check for uploads directory
    if [ -d "$PROJECT_ROOT/uploads" ]; then
        dirs_to_backup="$dirs_to_backup uploads"
    fi
    
    if [ ! -z "$dirs_to_backup" ]; then
        cd "$PROJECT_ROOT"
        tar -czf "$backup_file" $dirs_to_backup 2>/dev/null || true
        
        if [ -f "$backup_file" ]; then
            local size=$(du -h "$backup_file" | cut -f1)
            print_message "$GREEN" "Application data backup created: $backup_file (Size: $size)"
        fi
    else
        print_message "$YELLOW" "No application data directories found to backup"
    fi
}

# Function to backup environment configuration
backup_configuration() {
    print_message "$YELLOW" "Backing up configuration..."
    
    local backup_file="$BACKUP_DIR/${BACKUP_NAME}_config.tar.gz"
    
    cd "$PROJECT_ROOT"
    
    # Create list of config files to backup
    local config_files=""
    
    for file in .env .env.production .env.staging docker-compose.yml docker-compose.override.yml; do
        if [ -f "$file" ]; then
            config_files="$config_files $file"
        fi
    done
    
    if [ ! -z "$config_files" ]; then
        tar -czf "$backup_file" $config_files 2>/dev/null
        
        if [ -f "$backup_file" ]; then
            print_message "$GREEN" "Configuration backup created: $backup_file"
        fi
    fi
}

# Function to create backup metadata
create_backup_metadata() {
    local metadata_file="$BACKUP_DIR/${BACKUP_NAME}_metadata.json"
    
    cat > "$metadata_file" << EOF
{
    "timestamp": "$TIMESTAMP",
    "backup_name": "$BACKUP_NAME",
    "environment": "${APP_ENV:-production}",
    "database": {
        "host": "$DB_HOST",
        "port": "$DB_PORT",
        "name": "$DB_NAME"
    },
    "redis": {
        "host": "$REDIS_HOST",
        "port": "$REDIS_PORT"
    },
    "docker_images": $(docker images --format json | jq -s '.'),
    "git_commit": "$(git rev-parse HEAD 2>/dev/null || echo 'unknown')",
    "git_branch": "$(git branch --show-current 2>/dev/null || echo 'unknown')"
}
EOF
    
    print_message "$GREEN" "Backup metadata created: $metadata_file"
}

# Function to cleanup old backups
cleanup_old_backups() {
    print_message "$YELLOW" "Cleaning up old backups..."
    
    # Count current backups
    local backup_count=$(ls -1 "$BACKUP_DIR" | grep -E "backup_[0-9]{8}_[0-9]{6}" | wc -l)
    
    if [ $backup_count -gt $MAX_BACKUPS ]; then
        local backups_to_remove=$((backup_count - MAX_BACKUPS))
        print_message "$YELLOW" "Removing $backups_to_remove old backup(s)..."
        
        # Remove oldest backups
        ls -1t "$BACKUP_DIR" | grep -E "backup_[0-9]{8}_[0-9]{6}" | tail -n $backups_to_remove | while read backup_prefix; do
            # Remove all files with this prefix
            rm -f "$BACKUP_DIR/${backup_prefix}"*
            print_message "$YELLOW" "Removed old backup: $backup_prefix"
        done
    fi
}

# Function to upload backup to cloud storage (optional)
upload_to_cloud() {
    if [ ! -z "$AWS_S3_BUCKET" ]; then
        print_message "$YELLOW" "Uploading backup to S3..."
        
        for file in "$BACKUP_DIR/${BACKUP_NAME}"*; do
            if [ -f "$file" ]; then
                aws s3 cp "$file" "s3://$AWS_S3_BUCKET/backups/$(basename "$file")" \
                    --storage-class STANDARD_IA
                print_message "$GREEN" "Uploaded to S3: $(basename "$file")"
            fi
        done
    fi
    
    if [ ! -z "$GCS_BUCKET" ]; then
        print_message "$YELLOW" "Uploading backup to Google Cloud Storage..."
        
        for file in "$BACKUP_DIR/${BACKUP_NAME}"*; do
            if [ -f "$file" ]; then
                gsutil cp "$file" "gs://$GCS_BUCKET/backups/$(basename "$file")"
                print_message "$GREEN" "Uploaded to GCS: $(basename "$file")"
            fi
        done
    fi
}

# Function to verify backup
verify_backup() {
    print_message "$YELLOW" "Verifying backup..."
    
    local backup_valid=true
    
    # Check if PostgreSQL backup exists
    if [ ! -f "$BACKUP_DIR/${BACKUP_NAME}_postgres.sql.gz" ]; then
        print_message "$RED" "PostgreSQL backup not found!"
        backup_valid=false
    fi
    
    # Check if metadata exists
    if [ ! -f "$BACKUP_DIR/${BACKUP_NAME}_metadata.json" ]; then
        print_message "$RED" "Backup metadata not found!"
        backup_valid=false
    fi
    
    if [ "$backup_valid" = true ]; then
        print_message "$GREEN" "Backup verification passed"
        
        # Calculate total backup size
        local total_size=$(du -ch "$BACKUP_DIR/${BACKUP_NAME}"* | grep total | cut -f1)
        print_message "$GREEN" "Total backup size: $total_size"
    else
        print_message "$RED" "Backup verification failed!"
        exit 1
    fi
}

# Main backup process
main() {
    print_message "$GREEN" "========================================="
    print_message "$GREEN" "Email Optimizer Backup"
    print_message "$GREEN" "Backup Name: $BACKUP_NAME"
    print_message "$GREEN" "Timestamp: $TIMESTAMP"
    print_message "$GREEN" "========================================="
    
    # Create backup directory
    create_backup_directory
    
    # Perform backups
    backup_postgres
    backup_redis
    backup_application_data
    backup_configuration
    create_backup_metadata
    
    # Verify backup
    verify_backup
    
    # Upload to cloud (if configured)
    upload_to_cloud
    
    # Cleanup old backups
    cleanup_old_backups
    
    print_message "$GREEN" "========================================="
    print_message "$GREEN" "Backup completed successfully!"
    print_message "$GREEN" "Location: $BACKUP_DIR"
    print_message "$GREEN" "========================================="
    
    # Log backup
    echo "[$TIMESTAMP] Backup created: $BACKUP_NAME" >> "$PROJECT_ROOT/backups.log"
}

# Error handling
trap 'handle_error $? $LINENO' ERR

handle_error() {
    local exit_code=$1
    local line_number=$2
    
    print_message "$RED" "Backup failed at line $line_number with exit code $exit_code"
    
    # Clean up partial backup
    if [ ! -z "$BACKUP_NAME" ]; then
        rm -f "$BACKUP_DIR/${BACKUP_NAME}"* 2>/dev/null || true
    fi
    
    exit $exit_code
}

# Run main function
main