# Rollback Procedure

## Purpose

Rollback procedure for the intraday trading platform to restore previous state in case of failed deployment or critical issue.

## Pre-requisites

- Backup files preserved in `deployment/backups/` (must never be deleted)
- Access to Docker
- `.env` file with `POSTGRES_PASSWORD`
- Compose overlay file: `deployment/compose/compose.recovered.yml`

## Rollback Scenarios

### 1. API Container Failure

```bash
# Stop failed API container
docker compose -p compose -f deployment/compose/compose.yml -f deployment/compose/compose.recovered.yml stop api

# Restart API with previous image tag
docker compose -p compose -f deployment/compose/compose.yml -f deployment/compose/compose.recovered.yml up -d api
```

### 2. Database Recovery from Backup

```bash
# Stop database
docker compose -p compose -f deployment/compose/compose.yml -f deployment/compose/compose.recovered.yml stop db

# Restore from latest backup
# IMPORTANT: This requires stopping all services first
docker compose -p compose -f deployment/compose/compose.yml -f deployment/compose/compose.recovered.yml down db

# Find backup file
ls deployment/backups/*.pgdump

# Restore (adjust path as needed)
docker exec -i compose-db-1 psql -U "$POSTGRES_USER" -d trading < deployment/backups/recovered-original-20261108.pgdump

# Restart database
docker compose -p compose -f deployment/compose/compose.yml -f deployment/compose/compose.recovered.yml up -d db
```

### 3. Full Stack Rollback

```bash
# Stop all services
docker compose -p compose -f deployment/compose/compose.yml -f deployment/compose/compose.recovered.yml down

# Restore database from backup
docker exec -i compose-db-1 psql -U "$POSTGRES_USER" -d trading < deployment/backups/recovered-original-20261108.pgdump

# Start all services
docker compose -p compose -f deployment/compose/compose.yml -f deployment/compose/compose.recovered.yml up -d
```

## Critical Warnings

1. **Never run `docker compose down --volumes`** - This will permanently delete historical data and credentials
2. **Never delete files in `deployment/backups/`** - These are the only recovery points
3. **Never commit `.env`, `cookies.txt`, or `.pgdump` files** - These contain sensitive data
4. **Always use compose.recovered.yml overlay** - Without it, you lose access to historical data and credentials

## Verification After Rollback

```bash
# Check container status
docker compose -p compose ps

# Verify database connectivity
docker exec compose-db-1 bash -c 'PGPASSWORD="$POSTGRES_PASSWORD" psql -U "$POSTGRES_USER" -lqt'

# Verify historical data
docker exec compose-db-1 bash -c 'PGPASSWORD="$POSTGRES_PASSWORD" psql -U "$POSTGRES_USER" -d trading -c "SELECT COUNT(*) FROM historical_partitions"'

# Verify API health
curl http://127.0.0.1:8000/api/v1/health/ready

# Verify web proxy
curl http://127.0.0.1:8080/
```

## Recovery Time Objectives

- API restart: < 1 minute
- Database restore: 2-5 minutes (depending on backup size)
- Full stack recovery: 5-10 minutes

## Contact

Report any rollback to the team and document the reason in the commit message.
