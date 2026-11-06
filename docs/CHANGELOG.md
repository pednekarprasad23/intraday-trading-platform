# Changelog

## 2026-11-07 — Phase 1 local foundation

- Added containerized FastAPI, PostgreSQL, Redis and Vite/React frontend.
- Added Alembic foundation schema for user, instrument, provider mapping and audit records.
- Added interactive single-user bootstrap, Argon2id password hashing, expiring Redis sessions, logout, login rate limiting and same-origin mutation protection.
- Added read-only system status and searchable demo instrument API; demo fixture import is idempotent.
- Added tests, CI workflow, local setup guide and architecture decision record.
- Fixed authentication route paths, migration import path, and dependency security findings discovered during testing.
- Kept broker connectivity, orders, real market data, charts and AI outside Phase 1.
