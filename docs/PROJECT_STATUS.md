# Project status

Updated: 2026-11-07

## Phase 1 — implemented local foundation; review checkpoint

Implemented: React/Vite/TypeScript/Tailwind shell, typed API client, demo instrument search, login/logout, FastAPI health/readiness/status, PostgreSQL/Alembic tables, demo provider mappings, Redis opaque sessions and throttling, Argon2id bootstrap, security audit events, correlation IDs, local Compose, dependency locks, tests and GitHub Actions definition.

Safety: no live trading capability, broker SDK, real feed, strategy, AI research or paper execution simulator. Demo option metadata is explicitly a placeholder, not a real contract. Cloud/HTTPS/backup operations are deferred by approval.

## Verification actually performed

- Backend pytest: 4 passed (UTC, authentication/security flows, readiness and migration roundtrip). One dependency deprecation warning: Starlette recommends httpx2 instead of httpx for TestClient.
- Ruff lint and formatting: passed after fixes.
- Frontend TypeScript/production build: passed.
- Vitest API-client tests: 3 passed.
- npm audit: zero vulnerabilities after updating Vitest.
- pip-audit on resolved API environment: no known vulnerabilities after updating FastAPI/pytest/pip and removing unused multipart dependency.
- Linux Docker API and frontend builds: passed.
- Compose clean PostgreSQL migration/startup: passed after correcting Alembic import path.
- Readiness through web proxy: database ok, Redis ok.
- Demo seed run twice: seven instruments, no duplicates.
- PostgreSQL restart: seven rows persisted.
- HTTP end-to-end smoke: web, readiness, login, instrument/provider mapping list, status, logout and post-logout rejection passed using a temporary test account, subsequently removed.

## Remaining verification and limitations

- GitHub-hosted CI has not run; workflow exists, but no repository remote/push was performed.
- No browser visual/mobile review was performed. Responsive styles exist; UI rendering and component interaction coverage need strengthening.
- Frontend checks currently comprise TypeScript/build and API-client tests, not a dedicated ESLint suite. Backend uses Ruff but does not yet have a complete static type-check gate.
- Session expiry is tested as removal of Redis session state; a timed real-Redis expiry integration test remains desirable.
- Migration downgrade/upgrade tested on SQLite; PostgreSQL fresh upgrade and persistence verified, but PostgreSQL downgrade/restore drill remains pending.
- Local HTTP intentionally lacks Secure cookies; public deployment is not approved or safe with this configuration.
- Recovery/MFA, immutable database-enforced audit retention, operational alerts, cloud backups, container-image vulnerability scanning and external exposure review remain future hardening work.
- Lightweight Charts is intentionally not installed until charting has data and approved scope.

## Phase 2 progress — read-only market-data foundation

- User-selected direction recorded: Angel One API; MT5 remains a separate Windows-host bridge.
- Added broker-independent Quote/provider contracts, deterministic mock events, Decimal/timestamp validation, freshness monitor, heartbeat quality, bounded reconnect backoff and auth-failure state.
- Added offline Angel One decoder that rejects unknown tokens and unverified price units; no Angel One SDK, credentials, network connection or order capability was added.
- Added instrument metadata migration and validated idempotent import service; demo provenance is now data-driven rather than hard-coded in the API response.
- Installed and verified official Windows CPython 3.13.17 64-bit and `MetaTrader5==5.0.6231` cp313 wheel in an isolated bridge environment.
- Added a read-only, offline-tested MT5 facade with no network listener and no order methods. Real terminal connectivity remains unverified because no MT5 desktop installation was found and no account was connected.
- Tests: backend 8 passed; Windows bridge 1 passed. Backend has one existing httpx/Starlette deprecation warning.

## Next step

Review this Phase 1 checkpoint and remaining verification gaps before declaring the foundation production-ready (it is not). Do not begin Phase 2 without explicit approval. Phase 2 planning must settle the intended provider (DhanHQ versus original Angel One/MT5 vision), authorized data access and current official API capabilities.
