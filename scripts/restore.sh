#!/bin/bash
# Restore script for intraday-trading-platform
# Restores PostgreSQL database and Redis data from backup

set -e

# Configuration - use env vars or defaults
DB_CONTAINER="${DB_CONTAINER:-compose-db-1}"
API_CONTAINER="${API_CONTAINER:-compose-api-1}"
REDIS_CONTAINER="${REDIS_CONTAINER:-compose-redis-1}"
DB_NAME="${DB_NAME:-trading}"
DB_USER="${DB_USER:-trading}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1"
}

error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1"
}

usage() {
    echo "Usage: $0 <backup_file_path>"
    echo ""
    echo "Example:"
    echo "  $0 deployment/backups/backup_20261108_030000"
    echo ""
    echo "This will restore both PostgreSQL and Redis from the backup."
    exit 1
}

# Check arguments
if [ -z "$1" ]; then
    usage
fi

BACKUP_DIR="$1"

# Validate backup exists
PG_BACKUP="${BACKUP_DIR}.pgdump.gz"
REDIS_BACKUP="${BACKUP_DIR}.redis.rdb"

if [ ! -f "$PG_BACKUP" ]; then
    error "PostgreSQL backup not found: $PG_BACKUP"
    exit 1
fi

if [ ! -f "$REDIS_BACKUP" ]; then
    warn "Redis backup not found: $REDIS_BACKUP (proceeding with DB restore only)"
fi

# Critical data loss warning
echo ""
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║                    DANGER: DATA LOSS WARNING                      ║"
echo "╠══════════════════════════════════════════════════════════════════╣"
echo "║  This operation will:                                             ║"
echo "║  1. STOP the API server                                          ║"
echo "║  2. DROP and RECREATE the PostgreSQL database                    ║"
echo "║  3. RESTORE from backup                                            ║"
echo "║  4. RESTART the API server                                       ║"
echo "║                                                                   ║"
echo "║  ALL CURRENT DATA WILL BE PERMANENTLY DELETED!                    ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""

read -p "Type 'YES' to confirm data loss and proceed: " CONFIRM

if [ "$CONFIRM" != "YES" ]; then
    log "Restore cancelled by user"
    exit 0
fi

log "Starting restore process..."

# Stop API container (but keep DB and Redis running)
log "Stopping API server..."
docker stop "$API_CONTAINER" 2>/dev/null || true

# Allow containers to shut down gracefully
sleep 2

# Drop and recreate database
log "Dropping and recreating database..."
docker exec "$DB_CONTAINER" psql -U postgres -c "DROP DATABASE IF EXISTS ${DB_NAME};" || true
docker exec "$DB_CONTAINER" psql -U postgres -c "CREATE DATABASE ${DB_NAME};"

# Restore PostgreSQL backup
log "Restoring PostgreSQL database..."
gunzip -c "$PG_BACKUP" | docker exec -i "$DB_CONTAINER" pg_restore -U postgres -d "$DB_NAME" --clean --no-acl --no-owner

log "PostgreSQL restore completed"

# Restore Redis if backup exists
if [ -f "$REDIS_BACKUP" ]; then
    log "Restoring Redis data..."

    # Stop Redis
    docker stop "$REDIS_CONTAINER" 2>/dev/null || true
    sleep 1

    # Clear existing Redis data
    docker exec "$REDIS_CONTAINER" rm -f /data/dump.rdb 2>/dev/null || true

    # Copy restored RDB file
    docker cp "$REDIS_BACKUP" "${REDIS_CONTAINER}:/data/dump.rdb"

    # Set correct permissions
    docker exec "$REDIS_CONTAINER" chown redis:redis /data/dump.rdb 2>/dev/null || true

    log "Redis restore completed"
fi

# Start API container
log "Restarting API server..."
docker start "$API_CONTAINER"

# Wait for API to be ready
log "Waiting for API to be ready..."
sleep 5

# Verify restore
log "Verifying restore..."
HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/health/live 2>/dev/null || echo "000")

if [ "$HEALTH" = "200" ]; then
    log "✓ API health check passed"
else
    warn "API health check returned: $HEALTH (expected 200)"
fi

log "Restore completed successfully!"
log "Backup ID restored: $(basename "$BACKUP_DIR")"

exit 0