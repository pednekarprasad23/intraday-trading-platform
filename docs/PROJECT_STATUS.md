# Project status

Updated: 2026-11-07

## Phase 1 — implemented local foundation; review checkpoint

Implemented: React/Vite/TypeScript/Tailwind shell, typed API client, demo instrument search, login/logout, FastAPI health/readiness/status, PostgreSQL/Alembic tables, demo provider mappings, Redis opaque sessions and throttling, Argon2id bootstrap, security audit events, correlation IDs, local Compose, dependency locks, tests and GitHub Actions definition.

Phase 1 safety at that checkpoint: no live trading capability, broker SDK, real feed, strategy, AI research or paper execution simulator. Demo option metadata is explicitly a placeholder, not a real contract. Cloud/HTTPS/backup operations are deferred by approval.

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

## Phase 3 — offline historical option-candle vertical slice

Implemented a bounded, fixture-only import path for explicit synthetic 1m/5m option candles. The importer validates provider mapping and option metadata, explicit lowercase SHA-256, aware timestamps, deterministic IST session windows/alignment, Decimal OHLCV constraints, duplicates and conflicts; it never calls a broker or fills missing bars. Valid rows are stored in immutable content-addressed Parquet partitions under a persistent Compose volume, with PostgreSQL job/partition/gap metadata and idempotent source reruns. Authenticated paginated status, partition and gap summaries expose catalog data without filesystem paths. The demo command updates the illustrative option placeholder with non-tradeable metadata only.

Phase 3 limitations: no authoritative exchange calendar or holiday inference, no broker historical entitlement, no live historical fetcher, and no atomic cross-resource transaction between filesystem and DB. A DB failure after file publication leaves an operator-diagnosable orphan; `historical-orphans` reports but never deletes it. Corrections to an occupied partition require review. The fixture source is not retained by the importer.

Phase 3 verification: API image built successfully with PyArrow 23.0.1; Ruff check passed; backend pytest 16 passed with one pre-existing Starlette/httpx deprecation warning. Focused historical/migration tests passed (4). Frontend, Compose startup smoke, dependency audit, and full operational recovery drill were not rerun in this continuation.

## Phase 4 — deterministic research signals checkpoint

Added versioned frozen Decimal/UTC strategy contracts, pure EMA/RSI/ATR/VWAP indicators, an explicitly registered bounded option-premium reference rule, and an operator-only evaluation command against exact Phase 3 fixture provenance. Migration `0004` stores immutable configuration versions and exact accepted signal snapshots. No broker calls, order APIs, dynamic plugins or Phase 5 backtesting/catalog reader are included. See [Phase 4 strategies](PHASE_4_STRATEGIES.md). Backend verification: 21 tests passed (one existing Starlette/httpx deprecation warning); Ruff lint and format passed, including SQLite `0004` migration roundtrip. PostgreSQL migration/Compose smoke and audits were not performed in this checkout. The tiny Phase 3 fixtures cannot establish performance; no live prediction claims are made.

## Remaining verification and limitations

- GitHub-hosted CI has not been checked for the current uncommitted continuation; earlier Phase 1 and Phase 2 foundation commits were pushed to the configured origin.
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
- At the foundation checkpoint, added an offline Angel One decoder that rejects unknown tokens and unverified price units; the later read-only connector is described below.
- Added instrument metadata migration and validated idempotent import service; demo provenance is now data-driven rather than hard-coded in the API response.
- Installed and verified official Windows CPython 3.13.17 64-bit and `MetaTrader5==5.0.6231` cp313 wheel in an isolated bridge environment.
- At the foundation checkpoint, added a read-only, offline-tested MT5 facade with no network listener or order methods. Subsequent real-terminal verification is recorded below.
- Tests: backend 8 passed; Windows bridge 1 passed. Backend has one existing httpx/Starlette deprecation warning.

## Phase 2 read-only MT5 integration in progress

- 2026-11-07: verified the already-running Windows terminal using Python 3.13 and read-only MetaTrader5 calls. Initialization, connection, account availability and positions request succeeded; account identifiers and financial values were not printed.
- Expanded the bridge to account summary (without identifiers), positions, bounded raw deals, and bid/ask ticks. Added an outbound atomic snapshot worker, an optional read-only Compose mount, authenticated schema-validated API route, and separately expiring quote/snapshot display. No broker commands or Windows network listener exist.
- Verification to date: MT5 bridge 2 tests passed; backend 12 tests passed; Angel One worker 10 tests passed; frontend build and 3 API-client tests passed. npm audit and Angel One worker pip-audit found no known vulnerabilities. One pre-existing Starlette/httpx TestClient warning remains. Optional continuous worker-to-Compose end-to-end run, CI, and broader security review remain pending.
- Angel One server-side read-only authentication was successfully verified on 2026-11-07 using privately supplied values; no credential, token, account identifier or response payload was printed. The worker calls only documented login, instrument-search and LTP paths, writes an atomic snapshot, and exposes no listener or order method.
- Angel One LTP fetching remains disabled: an allowlisted NSE index search returned a broker-level unsuccessful response, so no token was verified and no LTP call was made. Instrument mapping and entitlement confirmation are still required. The official LTP response does not establish an exchange-event timestamp, so receipt time is shown and event freshness is marked unverified when absent.
- The registered callback URL is unused because the verified server-side Python login flow does not require a browser callback. Do not forward it to the dashboard or API.
- This is not production-ready. No live trading or paper execution simulator is enabled. Phase 3 requires separate approval.
