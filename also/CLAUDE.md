# Claude Code Project Instructions

Project: intraday-trading-platform

Build a modular Indian intraday options trading platform, initially for NIFTY. Stack: React/TypeScript/Vite/Tailwind/Lightweight Charts; Python/FastAPI/Pydantic/SQLAlchemy/Alembic; PostgreSQL, Redis, Parquet, DuckDB; Docker Compose. Keep strategy, market data, risk, order execution, and dashboard separate.

## Mandatory rules
- Plan and seek approval before each major phase. Preserve existing files.
- Never fabricate historical options candles, fills, broker capabilities, or performance results.
- Verify broker API behavior with current official documentation.
- Live trading OFF by default. Require explicit user approval and verified risk controls.
- Every order passes through central risk checks. Use idempotency and broker reconciliation; never blindly retry uncertain orders.
- Persist order lifecycle events and reconcile after restart.
- Separate paper/live data, credentials, and accounts.
- Use timezone-aware timestamps, Decimal for financial values, and validate historical data quality.
- Prevent look-ahead bias; model charges, slippage, liquidity, partial fills and ambiguous intrabar execution.
- Never commit secrets. Protect webhooks with authentication, freshness checks, and replay prevention.
- Implement automated tests and update docs at every milestone.

## Phases
1. Foundation and architecture
2. Broker market-data adapter and instruments
3. Historical data ingestion and quality
4. Python strategy plugins
5. Reproducible event-driven backtesting
6. Paper trading and risk controls
7. TradingView webhook integration
8. Live execution (separate approval gate)
9. Dashboard and analytics enhancements
10. Security, reliability, and deployment hardening

## First task
Inspect the directory without changing files. Propose architecture, folder structure, requirements, data model, MVP acceptance criteria, dependencies, and phase plan. Identify uncertainties. Wait for approval before coding.
