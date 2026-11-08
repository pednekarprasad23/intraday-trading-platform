# Backup and Restoring Guide

Step-by-step procedures for backing up and restoring the intraday-trading-platform.

---

## Table of Contents

1. [Automated Backups](#automated-backups)
2. [Manual Backups](#manual-backups)
3. [Manual Restores](#manual-restores)
4. [Restore Drills](#restore-drills)

---

## Automated Backups

### GitHub Actions Nightly Backup

A GitHub Actions workflow runs nightly at 03:00 UTC to create backups.

**Location:** `.github/workflows/nightly-backup.yml`

The workflow:
1. Builds the Docker stack
2. Runs the backup script
3. Stores backup artifacts

### Configuring Backup Retention

Set the retention period via environment variable:

```bash
export BACKUP_RETENTION_DAYS=7
```

Default is 7 days.

---

## Manual Backups

### Step 1: Run Backup Script

```bash
cd /path/to/intraday-trading-platform
./scripts/backup.sh
```

### Step 2: Verify Backup Files

Check that backup files were created:

```bash
ls -la deployment/backups/
```

Expected files:
```
backup_20261108_030000.pgdump.gz
backup_20261108_030000.redis.rdb
backup_20261108_030000.manifest.json
```

### Step 3: Verify Backup Integrity

The backup script automatically verifies PostgreSQL integrity. For manual verification:

```bash
# Verify PostgreSQL backup
gunzip -t deployment/backups/backup_*.pgdump.gz

# Check backup manifest
cat deployment/backups/backup_*.manifest.json
```

### Step 4: Backup Credential Key

For production use, also backup the encrypted credential key:

```bash
GPG_RECIPIENT=you@example.com ./scripts/backup-creds.sh
```

---

## Manual Restores

### Prerequisites

- Stop trading operations
- Notify users
- Ensure backup file exists
- Plan for data loss window

### Step 1: Stop API Service

```bash
docker stop compose-api-1
```

### Step 2: Locate Backup File

```bash
ls -la deployment/backups/backup_*.pgdump.gz
```

### Step 3: Run Restore Script

```bash
./scripts/restore.sh deployment/backups/backup_YYYYMMDD_HHMMSS
```

The script will:
1. Display data loss warning
2. Prompt for confirmation
3. Drop and recreate PostgreSQL database
4. Restore from backup
5. Restore Redis data
6. Restart API container
7. Verify health

### Step 4: Verify Restore

```bash
# Check API health
curl http://localhost:8080/api/v1/health/ready

# Check database connectivity
curl http://localhost:8080/api/v1/system/status

# Verify data via API
curl -b session=<token> http://localhost:8080/api/v1/instruments?limit=1
```

### Step 5: Post-Restore Validation

1. Verify user accounts exist
2. Check recent trades/positions
3. Verify strategy configurations
4. Test order placement (if applicable)

---

## Restore Drills

### Schedule

Monthly restore drills are recommended to verify backup integrity.

### Drill Procedure

1. **Create a test database:**

```bash
# Copy latest backup to test location
cp deployment/backups/latest_backup_*.pgdump.gz /tmp/test_backup.pgdump.gz
```

2. **Create temporary PostgreSQL container:**

```bash
docker run -d \
  --name temp-postgres \
  -e POSTGRES_PASSWORD=testpass \
  -p 5433:5432 \
  postgres:15
```

3. **Restore to temporary database:**

```bash
gunzip -c /tmp/test_backup.pgdump.gz | \
  docker exec -i temp-postgres \
  pg_restore -U postgres -d postgres --clean --no-owner
```

4. **Run smoke tests:**

```bash
# Test database connection
docker exec temp-postgres psql -U postgres -c "SELECT count(*) FROM backtest_report;"
```

5. **Clean up:**

```bash
docker stop temp-postgres
docker rm temp-postgres
rm /tmp/test_backup.pgdump.gz
```

### Automated Restore Drill

GitHub Actions weekly workflow runs restore drills.

**Location:** `.github/workflows/nightly-restore-drill.yml`

The workflow:
1. Creates temporary PostgreSQL container
2. Restores latest backup
3. Runs smoke tests
4. Reports success/failure

---

## Backup File Format

### PostgreSQL Backup

- **Format:** Custom format (pg_dump -F custom)
- **Extension:** `.pgdump.gz`
- **Compression:** gzip
- **Contents:** Full database dump including schemas and data

### Redis Backup

- **Format:** RDB snapshot
- **Extension:** `.redis.rdb`
- **Compression:** None (binary format)
- **Contents:** All keys and values from Redis

### Manifest

- **Format:** JSON
- **Extension:** `.manifest.json`
- **Contents:** Metadata about backup (timestamp, file sizes, retention)

---

## Common Issues

### Issue: Backup Directory Missing

**Symptom:** `scripts/backup.sh` fails with "No such file or directory"

**Solution:**
```bash
mkdir -p deployment/backups
chmod 755 deployment/backups
```

### Issue: Container Not Running

**Symptom:** `docker cp` fails with "No such container"

**Solution:**
```bash
# Check container status
docker ps -a | grep compose-

# Restart if needed
docker start compose-api-1 compose-redis-1
```

### Issue: Permission Denied

**Symptom:** `pg_restore: error: could not open database`

**Solution:**
```bash
# Check database user permissions
docker exec compose-api-1 psql -U postgres -c "\du"

# Recreate user if needed
docker exec compose-api-1 psql -U postgres -c \
  "CREATE USER postgres WITH SUPERUSER;"
```

### Issue: Backup Too Large

**Symptom:** Backup fails with disk space error

**Solution:**
1. Check disk space: `df -h`
2. Compress old backups: `gzip old_backup_file`
3. Clean old backups: Remove files older than retention period
4. Consider increasing storage

---

## Disaster Recovery

### Worst Case Scenario

If the primary server is lost:

1. **Provision new server** with same Docker configuration
2. **Install Docker** and clone repository
3. **Copy backup files** from external storage
4. **Run restore script** with latest backup
5. **Update DNS/Load balancer** to point to new server
6. **Notify users** and resume operations

### Recovery Time Objective (RTO)

- **Target:** 2 hours
- **Includes:** Provisioning, restore, verification

### Recovery Point Objective (RPO)

- **Target:** 24 hours
- **Includes:** All transactions up to last backup

---

## Best Practices

1. **Test restores regularly** - Monthly at minimum
2. **Encrypt backups** - Use GPG for credential backups
3. **Store backups offsite** - Cloud storage or external drive
4. **Monitor backup success** - Set up alerts for failures
5. **Document backup location** - Know where backups are stored
6. **Verify integrity** - Don't just check file existence