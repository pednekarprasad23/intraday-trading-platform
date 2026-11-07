# Changelog

## 2026-11-07 — Phase 4 strategies checkpoint

- Added frozen Decimal/UTC strategy contracts, pure indicators, bounded option-premium reference strategy and explicit built-in registry.
- Added operator-only fixture evaluation against Phase 3 provenance, immutable version/signal snapshots and `0004` migration; no broker/order or Phase 5 functionality.
- Documented research-only scope and rejection behavior in [Phase 4 strategies](PHASE_4_STRATEGIES.md).

## 2026-11-07 — Phase 3 offline fixture ingestion checkpoint

- Added explicit IST 1m/5m synthetic option CSV validation, source hashing, duplicate/conflict rejection and missing-slot reports with no synthetic gap filling.
- Added immutable content-addressed Parquet partitions, import/partition/gap catalog migration, idempotent operator command, orphan diagnostic, authenticated bounded read-only summaries, and persistent Compose volume.
- Kept broker calls, strategy/backtest, order paths, data entitlements and execution flags out of scope.

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
- Added separately isolated read-only MT5 bridge facade and tests; real terminal connectivity was pending at the foundation checkpoint.

## 2026-11-07 — Read-only MT5 continuation in progress

- Confirmed the installed Windows MT5 terminal connects through Python 3.13 with read-only account and positions availability checks; no identifying or financial values were printed.
- Extended the allowlisted bridge and added an outbound atomic snapshot worker with no network listener or command channel.
- Added a disabled-by-default Compose read-only mount, authenticated API snapshot validation and expiry, and a read-only UI showing account, positions, bounded raw history and bid/ask provenance.
- Angel One was initially offline; no order capability was introduced. Optional end-to-end Compose activation and host ACL review remain pending.

## 2026-11-07 — Angel One read-only connector progress

- Verified the official server-side login and LTP paths; the registered browser callback is not used.
- Added a separate outbound-only worker with private process credentials, in-memory TOTP/JWT, bounded instrument list, and a secret-free atomic snapshot. Added disabled-by-default read-only API mount/route and UI with explicit timestamp-quality labels.
- Performed a redacted real authentication test successfully using private credentials. An allowlisted NSE index search returned a broker-level unsuccessful response; no token was verified and no LTP call was made. Added offline coverage of both success-envelope shapes and failure rejection. Verified instrument mapping and entitlement remain pending; no Angel One order call or route exists.
