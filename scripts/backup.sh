#!/bin/bash
# Backup script for intraday-trading-platform
# Creates dated backups of PostgreSQL database and Redis data

set -e

# Configuration - use .env values or defaults
DB_CONTAINER="${DB_CONTAINER:-compose-db-1}"
API_CONTAINER="${API_CONTAINER:-compose-api-1}"
REDIS_CONTAINER="${REDIS_CONTAINER:-compose-redis-1}"
DB_NAME="${DB_NAME:-trading}"
DB_USER="${DB_USER:-trading}"
BACKUP_DIR="${BACKUP_DIR:-deployment/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/backup_${TIMESTAMP}"

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

# Create backup directory
mkdir -p "$BACKUP_DIR"

log "Starting backup process..."
log "Database: ${DB_NAME}, User: ${DB_USER}, Container: ${DB_CONTAINER}"

# PostgreSQL backup
log "Backing up PostgreSQL database..."
docker exec "$DB_CONTAINER" pg_dump -U "$DB_USER" -F custom -d "$DB_NAME" > "${BACKUP_FILE}.pgdump"

# Compress PostgreSQL dump
gzip -f "${BACKUP_FILE}.pgdump" -c > "${BACKUP_FILE}.pgdump.gz"
rm "${BACKUP_FILE}.pgdump"

log "PostgreSQL backup created: ${BACKUP_FILE}.pgdump.gz"

# Redis backup
log "Backing up Redis data..."
docker exec "$REDIS_CONTAINER" redis-cli --rdb /data/dump.rdb 2>/dev/null || warn "Redis RDB save returned non-zero"
docker cp "${REDIS_CONTAINER}:/data/dump.rdb" "${BACKUP_FILE}.redis.rdb" 2>/dev/null || warn "Could not copy Redis RDB"

log "Redis backup created: ${BACKUP_FILE}.redis.rdb"

# Create backup manifest
cat > "${BACKUP_FILE}.manifest.json" << EOF
{
  "timestamp": "$(date -Iseconds)",
  "backup_id": "${TIMESTAMP}",
  "database": "${DB_NAME}",
  "components": {
    "postgresql": {
      "file": "backup_${TIMESTAMP}.pgdump.gz",
      "size_bytes": $(stat -c%s "${BACKUP_FILE}.pgdump.gz" 2>/dev/null || stat -f%z "${BACKUP_FILE}.pgdump.gz" 2>/dev/null || echo 0)
    },
    "redis": {
      "file": "backup_${TIMESTAMP}.redis.rdb",
      "size_bytes": $(stat -c%s "${BACKUP_FILE}.redis.rdb" 2>/dev/null || stat -f%z "${BACKUP_FILE}.redis.rdb" 2>/dev/null || echo 0)
    }
  },
  "retention_days": ${RETENTION_DAYS}
}
EOF

log "Backup manifest created: ${BACKUP_FILE}.manifest.json"

# Verify PostgreSQL backup integrity
log "Verifying PostgreSQL backup integrity..."
if gzip -t "${BACKUP_FILE}.pgdump.gz" 2>/dev/null; then
    log "PostgreSQL backup integrity verified"
else
    error "PostgreSQL backup integrity check failed"
    exit 1
fi

# List backups for cleanup
log "Current backups:"
ls -lh "${BACKUP_DIR}"/backup_*.pgdump.gz 2>/dev/null | sed 's/^/  /' || echo "  (none)"

# Cleanup old backups
log "Cleaning up backups older than ${RETENTION_DAYS} days..."
find "$BACKUP_DIR" -name "backup_*.pgdump.gz" -mtime +${RETENTION_DAYS} -delete 2>/dev/null || true
find "$BACKUP_DIR" -name "backup_*.redis.rdb" -mtime +${RETENTION_DAYS} -delete 2>/dev/null || true
find "$BACKUP_DIR" -name "backup_*.manifest.json" -mtime +${RETENTION_DAYS} -delete 2>/dev/null || true

# Remove orphan Redis dumps (original location)
docker exec "$REDIS_CONTAINER" rm -f /data/dump.rdb 2>/dev/null || true

log "Backup completed successfully!"
log "Total backup size: $(du -sh ${BACKUP_DIR} 2>/dev/null | cut -f1)"

exit 0