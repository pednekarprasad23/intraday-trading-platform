# Release Readiness Document

**Date:** 2026-11-08  
**Version:** 1.0  
**Status:** READY FOR DEPLOYMENT (with reservations)

---

## Overview

This document provides release readiness evidence for the Intraday Research Platform. It covers operational capabilities, resilience measures, security posture, and known limitations.

---

## Feature/Limitation Matrix

| Capability | Status | Notes |
|------------|--------|-------|
| **Historical Market Data** | OPERATIONAL | Dhan exact-import available for verified contracts |
| **Research Rankings** | OPERATIONAL | Strategy-based candidate ranking with evidence chain |
| **Instrument Mappings** | OPERATIONAL | NIFTY/F&O, equities, MT5 contracts mapped |
| **Paper Trading** | SIMULATED | No broker execution, research-only |
| **Backtesting** | OPERATIONAL | Walk-forward analysis with cost modeling |
| **Broker Orders** | DISABLED | No demo/live execution authorized |
| **Kill Switch** | OPERATIONAL | Persistent, auditable order blocking |
| **Risk Controls** | OPERATIONAL | Capital/exposure/position limits enforced |

---

## Security Posture

### Authentication

- **Production:** Fail-closed (requires valid credentials)
- **Development:** `AUTH_DISABLED=true` for localhost only
- **Secrets:** Encrypted credential storage, never in logs
- **Session:** JWT-based, time-limited

### Data Protection

- **Credentials:** Stored encrypted, loaded from files
- **API Keys:** Never in source code or environment variables
- **Database:** PostgreSQL with connection pooling
- **Backups:** Encrypted, retention-managed

### Paper/Live Isolation

- **Paper Account:** `live_trading_enabled=False`
- **Kill Switch:** Default ARMED (orders allowed)
- **UI Boundaries:** "RESEARCH ONLY · SIMULATED · NO BROKER ORDER"
- **Order States:** PERSISTED, idempotent, restart-recoverable

---

## Operational Capabilities

### Backup/Restore

**Scripts Available:**
- `scripts/backup.sh` - Automated PostgreSQL + Redis backup
- `scripts/restore.sh` - Safe database restore with warnings

**Configuration:**
- `BACKUP_DIR` - Default: `deployment/backups`
- `RETENTION_DAYS` - Default: 7
- `DB_CONTAINER` - Default: `compose-db-1`
- `REDIS_CONTAINER` - Default: `compose-redis-1`

**Backup Contents:**
- PostgreSQL database dump (gzip compressed)
- Redis RDB snapshot
- Manifest JSON with metadata

### Monitoring

**Endpoints:**
- `/api/v1/monitoring/health` - System health status
- `/api/v1/monitoring/metrics` - Request counts, uptime
- `/api/v1/monitoring/backups` - Available backups (auth required)

**Metrics Tracked:**
- Request totals/success/error
- Active sessions
- Database connections
- Redis connections

### Health Checks

**Dependencies Monitored:**
- PostgreSQL database
- Redis cache
- API response time

**Status Indicators:**
- `healthy` - All systems operational
- `degraded` - Some dependencies unavailable
- `unhealthy` - Critical failures

---

## Startup/Recovery Procedures

### Fresh Startup

1. **Verify volumes preserved:**
   ```bash
   docker volume ls | grep intraday
   ```

2. **Start services:**
   ```bash
   docker compose up -d
   ```

3. **Verify health:**
   ```bash
   curl http://localhost:8080/api/v1/monitoring/health
   ```

4. **Restore from backup if needed:**
   ```bash
   ./scripts/restore.sh deployment/backups/backup_TIMESTAMP
   ```

### Provider Credential Rotation

1. **Update encrypted credential file**
2. **Restart API container:**
   ```bash
   docker compose restart api
   ```
3. **Verify connectivity:**
   ```bash
   curl http://localhost:8000/api/v1/market_data/coverage
   ```

### Stale Feed Response

**Behavior:**
- Historical data shows last known state
- Real-time endpoints return cached data with freshness timestamp
- UI displays "DATA FRESHNESS WARNING" banner

---

## Rollback Procedures

### Application Rollback

1. **Identify previous image tag**
2. **Update Compose configuration**
3. **Pull previous image:**
   ```bash
   docker pull intraday-api:previous-tag
   ```
4. **Restart services:**
   ```bash
   docker compose up -d
   ```

### Database Rollback

1. **Identify backup timestamp**
2. **Stop API service:**
   ```bash
   docker compose stop api
   ```
3. **Execute restore:**
   ```bash
   ./scripts/restore.sh deployment/backups/backup_TIMESTAMP
   ```
4. **Restart API:**
   ```bash
   docker compose start api
   ```

**WARNING:** Database restore is destructive. Verify backup integrity first.

---

## Incident Escalation

### Severity Levels

| Level | Description | Response Time |
|-------|-------------|---------------|
| P1 - Critical | System down, data loss | Immediate |
| P2 - High | Partial outage, degraded | 1 hour |
| P3 - Medium | Non-critical feature | 4 hours |
| P4 - Low | Cosmetic, enhancement | Next sprint |

### Escalation Path

1. **On-call operator** - Initial response
2. **Engineering lead** - P1/P2 incidents
3. **Platform team** - Infrastructure issues
4. **Management** - Customer-impacting incidents

---

## Known Limitations

### Gap Visualization

**Status:** PARTIAL

**Details:**
- Backend has `/gaps` endpoint
- Frontend calculates gaps for candle spacing
- No dedicated visual gap marker
- **Impact:** Visual representation of missing data incomplete
- **Target:** Phase 8 implementation

### Browser Smoke Testing

**Status:** MANUAL RELEASE GATE

**Details:**
- No automated browser test infrastructure
- Manual verification required for all UI views
- **Impact:** Cannot fully automate release verification
- **Workaround:** Documented manual steps in `BROWSER_SMOKE_GATE.md`

### Real-Time Data

**Status:** SIMULATED

**Details:**
- No live market data feeds configured
- Historical data only
- Paper trading uses simulated execution
- **Impact:** No real-time trading capability
- **Authorization:** Not authorized in current roadmap

---

## Pre-Flight Checklist

### Security

- [ ] `AUTH_DISABLED=false` in production
- [ ] Credential key file present and accessible
- [ ] No hardcoded secrets in source
- [ ] No secrets in logs or metrics

### Data Integrity

- [ ] PostgreSQL migrations up to date
- [ ] Backup verified and restorable
- [ ] Redis persistence enabled
- [ ] Database schema validated

### Operational

- [ ] Health check endpoint responsive
- [ ] Monitoring endpoints accessible
- [ ] Backup script executable
- [ ] Restore procedure documented

### Performance

- [ ] API response time < 500ms
- [ ] Database connection pool adequate
- [ ] Redis cache responsive
- [ ] No memory leaks observed

---

## Deployment Recommendations

### Minimum Requirements

- **PostgreSQL:** 16.x with persistence
- **Redis:** 7.x with RDB persistence
- **API:** Python 3.12+
- **Frontend:** Nginx static serving
- **Network:** Same-origin proxy configuration

### Production Checklist

1. [ ] Enable `AUTH_DISABLED=false`
2. [ ] Configure production credential key
3. [ ] Set up backup retention (7+ days)
4. [ ] Configure monitoring alerts
5. [ ] Document rollback procedure
6. [ ] Test restore procedure
7. [ ] Verify health check endpoints
8. [ ] Review firewall rules
9. [ ] Configure log retention
10. [ ] Document emergency contacts

---

## Release Notes

### Version 1.0 (Current)

**Features:**
- Historical market data viewer with OHLCV charting
- Research rankings with strategy-based scoring
- Instrument mappings for NIFTY/F&O, equities, MT5
- Paper trading with kill switch and risk controls
- Backtesting with walk-forward analysis
- Comprehensive monitoring and health checks

**Known Issues:**
- Gap visualization incomplete (PARTIAL)
- Browser smoke testing requires manual verification
- No real-time market data
- No broker execution

**Backward Compatibility:**
- API compatible with v1.0
- Database migrations forward-compatible
- Frontend requires cache invalidation after update

---

**Last Updated:** 2026-11-08  
**Approved By:** Platform Engineering  
**Next Review:** 2026-12-08
