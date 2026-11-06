# First Development Sprint
## Sprint 0/1 – Cloud Foundation and Vertical Slice

**Suggested duration:** 1–2 weeks for a beginner working part-time; adjust to actual availability.  
**Objective:** Deliver a running cloud-hosted skeleton with secure access, database connectivity, instrument master and a working dashboard using synthetic/demo data.  
**Explicitly out of scope:** Live broker orders, production market feed, AI-driven trade recommendations.

## 1. Sprint outcome

At the end of this sprint:
- A private Git repository exists.
- A cloud Linux VM runs the application using Docker Compose.
- HTTPS access to the web UI works.
- FastAPI health endpoints work.
- PostgreSQL and Redis are private to the Docker network.
- A user can log in.
- Instrument master can be seeded/imported from a fixture.
- Dashboard displays instrument list and system status.
- Automated tests and basic logs are available.
- No broker secrets or live trading credentials are required.

## 2. Cloud deployment baseline

Use a small Linux VM with:
- Fixed public IPv4 if the selected provider offers it economically.
- Ubuntu LTS or another supported stable Linux distribution.
- Docker Engine and Docker Compose plugin.
- 2 vCPU and 4 GB RAM as a starting test size; increase if Next.js build or database load requires it.
- Persistent disk sized for OS, containers and a modest development database.
- HTTPS reverse proxy.
- Firewall allowing HTTPS publicly and SSH only from administrator IP/VPN.
- No public database or Redis ports.

This is a starting estimate, not a guaranteed production size. Compare total VM, disk, fixed IP, bandwidth, snapshot and backup costs before selecting a provider. For the first sprint, a cloud free-credit VM is acceptable if it supports persistent storage and the required networking.

## 3. Work breakdown

### Task 1 – Repository and engineering conventions
- Create private Git repository.
- Add README, `.gitignore`, `.env.example`, licence/dependency notes.
- Add formatting/linting configuration.
- Add branch naming and commit conventions.
- Add `docs/` and place approved architecture documents there.

**Done when:** Clean clone can be configured without copying secrets from another machine.

### Task 2 – Backend skeleton
- Create FastAPI application.
- Add `/api/v1/health/live` and `/api/v1/health/ready`.
- Add Pydantic settings.
- Add structured logging and request correlation ID.
- Add Alembic.
- Add pytest.

**Done when:** API starts in Docker, health checks work and tests pass.

### Task 3 – Database and Redis
- Add PostgreSQL service.
- Add Redis service.
- Create first Alembic migration for users, instruments, provider symbols and audit logs.
- Add database readiness check.
- Keep database/Redis ports internal only.

**Done when:** API can connect, run migration and read/write a test instrument.

### Task 4 – Frontend skeleton
- Create Next.js + TypeScript app.
- Add responsive app shell, navigation and login screen.
- Add dashboard cards for feed status, market overview and top opportunities.
- Add API client with typed response models.
- Add empty/loading/error states.

**Done when:** UI works on desktop and mobile browser widths and gets health/status from API.

### Task 5 – Authentication
- Implement single-user bootstrap flow.
- Hash password with Argon2id.
- Use secure HttpOnly cookies.
- Add logout and session expiry.
- Rate-limit login.
- Do not expose registration publicly; create the initial account through a protected bootstrap command or one-time setup.

**Done when:** Unauthenticated requests are rejected and session cookie is not readable by JavaScript.

### Task 6 – Instrument master
- Define canonical instrument Pydantic model.
- Create seed fixture for representative instruments: NIFTY spot, BANKNIFTY spot, SENSEX spot, FINNIFTY spot, one illustrative option contract, Gold contract placeholder and BTC symbol placeholder.
- Clearly mark fixtures as DEMO and not execution-enabled.
- Add list/search endpoint and frontend table.
- Add provider mapping model.

**Done when:** User can view/search seeded instruments and each mapping has provider and eligibility flags.

### Task 7 – CI and quality checks
- Add GitHub Actions for lint, type check and tests.
- Add dependency pinning/lockfile.
- Add container health checks.
- Add basic dependency vulnerability scan if available in free tier.

**Done when:** Pull request checks run automatically and fail on test/lint errors.

### Task 8 – Cloud deployment
- Provision VM.
- Configure firewall and SSH.
- Deploy Compose stack.
- Configure TLS reverse proxy and domain if available.
- Configure encrypted database backup to a separate destination.
- Test restart/redeploy.

**Done when:** Application is reachable over HTTPS and database survives container restart.

## 4. Suggested initial API contracts

### `GET /api/v1/health/live`
```json
{"status":"ok"}
```

### `GET /api/v1/health/ready`
```json
{
  "status":"ready",
  "dependencies":{
    "database":"ok",
    "redis":"ok"
  }
}
```

### `GET /api/v1/instruments`
Query: `asset_class`, `exchange`, `search`, `active`, `limit`, `offset`.

Response:
```json
{
  "items":[
    {
      "id":"uuid",
      "canonical_symbol":"NIFTY",
      "display_name":"NIFTY 50",
      "asset_class":"INDEX",
      "exchange":"NSE",
      "is_active":true,
      "data_available":false,
      "execution_enabled":false
    }
  ],
  "total":1
}
```

### `GET /api/v1/system/status`
Returns application version, environment, service health and connector status. Never return secrets or full account identifiers.

## 5. Initial screens

1. Login.
2. Dashboard.
3. Market watch / instrument master.
4. System status.
5. Settings placeholder.

Dashboard cards should clearly say `DEMO DATA` until a real provider is connected. Do not display fabricated numbers as live prices.

## 6. Acceptance test checklist

- [ ] Fresh clone and setup instructions work.
- [ ] No secrets committed.
- [ ] Docker Compose starts all services.
- [ ] API live and ready health checks pass.
- [ ] Database migration applies to empty database.
- [ ] Instrument seed is idempotent.
- [ ] Login succeeds with correct password.
- [ ] Login fails with incorrect password.
- [ ] Session expires and logout invalidates it.
- [ ] Unauthenticated API access is rejected.
- [ ] Instrument list/search works.
- [ ] Dashboard displays service status.
- [ ] UI remains usable at mobile width.
- [ ] PostgreSQL data survives container restart.
- [ ] Backup is created and restore procedure documented.
- [ ] CI runs lint and tests successfully.

## 7. Sprint exit gate

Do not begin live market data integration until:
- Cloud deployment is stable.
- Instrument identifiers and provider mapping design are reviewed.
- UTC/timezone conventions are tested.
- Data source terms and API access are confirmed.
- Secrets handling is in place.

Do not begin live order execution until paper trading, risk checks, idempotency, order reconciliation, static IP/broker onboarding and regulatory requirements have been validated.

## 8. Next sprint preview – market data vertical slice

1. Implement common `MarketDataProvider` interface.
2. Implement one provider connector in read-only mode.
3. Subscribe to a small approved instrument set.
4. Normalise quotes and timestamps.
5. Build 1m/5m candles.
6. Persist candles and display a live chart.
7. Add feed heartbeat, stale-data alert and reconnect tests.
8. Add historical importer for one instrument/timeframe/date range.
9. Compare broker historical candles with an independent licensed source and document differences.

Keep the first market-data sprint narrow. Prove one end-to-end path before adding every market and contract.
