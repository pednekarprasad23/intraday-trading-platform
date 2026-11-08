# Operations Guide

This document covers operational procedures for the intraday-trading-platform.

## Table of Contents

1. [Backup and Restore](#backup-and-restore)
2. [Health Checks](#health-checks)
3. [Monitoring Endpoints](#monitoring-endpoints)
4. [Strategy Lifecycle Management](#strategy-lifecycle-management)
5. [Troubleshooting](#troubleshooting)

---

## Backup and Restore

### Backup Schedule

Backups are created **daily at 03:00 UTC** via GitHub Actions or manually via script.

| Component | Location | Retention |
|-----------|----------|-----------|
| PostgreSQL | `deployment/backups/` | 7 days |
| Redis | `deployment/backups/` | 7 days |
| Credentials | `deployment/backups/` | 7 days |

### Manual Backup

```bash
# Run backup script
./scripts/backup.sh

# Or with custom settings
BACKUP_DIR=/path/to/backups RETENTION_DAYS=14 ./scripts/backup.sh
```

Backup files:
- `backup_YYYYMMDD_HHMMSS.pgdump.gz` - PostgreSQL dump
- `backup_YYYYMMDD_HHMMSS.redis.rdb` - Redis RDB snapshot
- `backup_YYYYMMDD_HHMMSS.manifest.json` - Backup metadata

### Manual Restore

**WARNING: This will permanently delete all current data.**

```bash
# List available backups
ls -la deployment/backups/

# Restore from backup
./scripts/restore.sh deployment/backups/backup_YYYYMMDD_HHMMSS
```

The restore script will:
1. Stop the API container
2. Drop and recreate the PostgreSQL database
3. Restore from backup
4. Restore Redis data
5. Restart the API

### Credential Backup

```bash
# Backup credential key
./scripts/backup-creds.sh

# With GPG encryption (requires GPG key configured)
GPG_RECIPIENT=you@example.com ./scripts/backup-creds.sh
```

---

## Health Checks

### Live Health Check

`GET /api/v1/health/live`

Returns `200 OK` when the service is running.

```bash
curl http://localhost:8080/api/v1/health/live
# {"status": "ok"}
```

### Ready Health Check

`GET /api/v1/health/ready`

Returns `200 OK` when all dependencies are healthy. Returns `503` if unhealthy.

```bash
curl http://localhost:8080/api/v1/health/ready
# {"status": "ready", "dependencies": {"database": "ok", "redis": "ok"}}
```

### Monitoring Endpoints (Requires Auth)

#### System Status

`GET /api/v1/system/status`

```bash
curl -b session=<token> http://localhost:8080/api/v1/system/status
```

Response:
```json
{
  "version": "0.1.0",
  "environment": "development",
  "trading_mode": "PAPER_TRADING",
  "live_trading_enabled": false,
  "market_data": "connected",
  "market_provider": "DHAN",
  "dependencies": {"database": "ok", "redis": "ok"}
}
```

#### Full Health Check

`GET /api/v1/monitoring/health`

```bash
curl -b session=<token> http://localhost:8080/api/v1/monitoring/health
```

Response:
```json
{
  "status": "healthy",
  "timestamp": "2026-11-08T03:00:00.000000",
  "dependencies": {
    "database": "ok",
    "redis": "ok",
    "api": "ok"
  },
  "response_time_ms": 12.5
}
```

#### Prometheus Metrics

`GET /api/v1/monitoring/metrics`

Returns JSON metrics for monitoring:

```bash
curl http://localhost:8080/api/v1/monitoring/metrics
```

#### Prometheus Text Format

`GET /api/v1/monitoring/metrics/prometheus`

For Prometheus scraping:

```bash
curl http://localhost:8080/api/v1/monitoring/metrics/prometheus
# HELP intraday_requests_total Total number of requests
# TYPE intraday_requests_total counter
# intraday_requests_total 150
# ...
```

#### Backup List

`GET /api/v1/monitoring/backups`

Requires authentication. Lists available backups.

```bash
curl -b session=<token> http://localhost:8080/api/v1/monitoring/backups
```

#### Strategy Versions

`GET /api/v1/monitoring/strategy/versions`

Lists all strategies and their versions:

```bash
curl http://localhost:8080/api/v1/monitoring/strategy/versions
```

---

## Strategy Lifecycle Management

### Strategy States

| State | Description |
|-------|-------------|
| `draft` | In development, not ready for production |
| `testing` | Under testing, limited backtesting |
| `live` | Deployed to production |
| `archived` | Retired, no longer used |

### Promotion Process

1. **Draft → Testing**
   - Complete backtesting with walk-forward analysis
   - Verify performance metrics
   - Run paper trading simulation

2. **Testing → Live**
   - Code review complete
   - Risk limits configured
   - Monitoring alerts set up
   - **Explicit approval required**

3. **Live → Archived**
   - Superceded by newer version
   - Remove from active trading
   - Retain for audit purposes

### Performance Drift Detection

```python
from app.monitoring.performance import detect_drift

result = detect_drift("strategy_id", threshold=0.1)
# Returns drift analysis comparing recent vs historical
```

---

## Troubleshooting

### Database Unhealthy

```bash
# Check database container
docker ps | grep postgres

# Check logs
docker logs compose-api-1

# Manual connection test
docker exec compose-api-1 python -c "from sqlalchemy import text; from app.database import engine; print(engine.connect().execute(text('SELECT 1')).fetchone())"
```

### Redis Unhealthy

```bash
# Check Redis container
docker ps | grep redis

# Test connection
docker exec compose-api-1 python -c "import redis; r = redis.Redis.from_url('redis://localhost:6379'); print(r.ping())"
```

### Authentication Failing (403)

This typically indicates:
1. **Session token expired** - Login again
2. **Origin mismatch** - Check `BASE_URL` matches frontend origin
3. **CORS misconfiguration** - Check CORS settings

```bash
# Verify session cookie
curl -v http://localhost:8080/api/v1/auth/login -H "Origin: http://localhost:8080"
```

### Backup Failures

Check backup script output:

```bash
# Check if Docker containers are running
docker ps | grep -E "(compose-api|compose-redis)"

# Check backup directory permissions
ls -la deployment/backups/

# Run backup with verbose output
bash -x ./scripts/backup.sh
```

### API Not Responding

```bash
# Restart API container
docker restart compose-api-1

# Check logs for errors
docker logs -f compose-api-1

# Verify port is bound
netstat -an | grep 8080
```

### Missing Backups

```bash
# Create backup directory if missing
mkdir -p deployment/backups

# Set permissions
chmod 755 deployment/backups

# Run backup manually
./scripts/backup.sh
```

---

## Incident Response

### If Health Checks Fail

1. **Identify the failing component** - Check `/api/v1/monitoring/health` response
2. **Check container status** - `docker ps`
3. **View logs** - `docker logs <container_name>`
4. **Restart unhealthy container** - `docker restart <container_name>`
5. **Verify recovery** - Re-check health endpoint

### If Database Is Corrupted

1. **Stop API** - `docker stop compose-api-1`
2. **Restore from latest backup**
3. **Start API** - `docker start compose-api-1`
4. **Verify data integrity** - Check endpoints

### If Redis Data Is Lost

1. Check if backup exists
2. Restore Redis from backup:
   ```bash
   docker stop compose-redis-1
   docker cp deployment/backups/backup_*.redis.rdb compose-redis-1:/data/dump.rdb
   docker start compose-redis-1
   ```

---

## Contact

For operational issues requiring escalation, contact the platform team.

Document version: 2026-11-08