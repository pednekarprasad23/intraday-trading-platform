# Changelog

## 2026-11-07 — Phase 1 local foundation

- Added containerized FastAPI, PostgreSQL, Redis and Vite/React frontend.
- Added Alembic foundation schema for user, instrument, provider mapping and audit records.
- Added interactive single-user bootstrap, Argon2id password hashing, expiring Redis sessions, logout, login rate limiting and same-origin mutation protection.
- Added read-only system status and searchable demo instrument API; demo fixture import is idempotent.
- Added tests, CI workflow, local setup guide and architecture decision record.
- Fixed authentication route paths, migration import path, and dependency security findings discovered during testing.
- Kept broker connectivity, orders, real market data, charts and AI outside Phase 1.

## 2026-11-07 — Phase 2 read-only foundation progress

- Recorded Angel One as the selected provider direction and documented official-source verification limits.
- Added provider-independent market-data contracts, deterministic mock provider, freshness/reconnect monitor, and offline Angel One decoder.
- Added instrument metadata migration/import validation and data-driven demo provenance.
- Installed Python 3.13.17 and verified the official MetaTrader5 cp313 Windows wheel in an isolated environment.
- Added separately isolated read-only MT5 bridge facade and tests; real terminal connectivity remains pending.
