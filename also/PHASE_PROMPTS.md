# Phase prompts for Claude Code

Use one prompt at a time. Require a working testable checkpoint and a summary before proceeding.

## Phase 1
Implement repository structure, Docker Compose, FastAPI health endpoints, React dashboard shell, PostgreSQL migrations, configuration, authentication scaffold, CI and tests. Do not connect a real broker. Provide commands and passing test output.

## Phase 2
Implement broker-independent market data interfaces and a DhanHQ adapter based only on verified current official API documentation. Include instrument master, expiry metadata, reconnection, freshness checks, mock provider and tests. No live orders.

## Phase 3
Implement historical 1m/5m option candle ingestion with provider provenance, Parquet partitioning, deduplication, gap reports, IST session handling, validation and import progress. Never synthesize missing data. Demonstrate sample import using test fixtures.

## Phase 4
Implement versioned strategy plugin interface, signals, indicator utilities, configuration validation, isolated execution and deterministic unit tests. Strategies must not call brokers.

## Phase 5
Implement event-driven option-premium backtesting with no look-ahead, configurable fill assumptions, slippage, costs, expiry-aware contract selection, missing-data warnings, reproducibility metadata, walk-forward testing and analytics. Demonstrate with fixtures.

## Phase 6
Implement paper broker with realistic order lifecycle, partial fills, risk checks, persistence, restart recovery and a clearly marked paper dashboard. Test rejected, duplicate, delayed and uncertain orders.

## Phase 7
Implement authenticated TradingView webhook ingestion with schema validation, stale/replayed signal rejection, strategy mapping, audit logs, rate limits and paper execution only. Demonstrate end-to-end with sample payloads.

## Phase 8
Plan live broker order execution; do not activate it. First present official API compatibility matrix, operational risks, kill-switch design, reconciliation tests, position limits and live-readiness checklist. Wait for explicit approval before any real order-capable credentials or live orders.

## Phase 9
Implement options chain, charting, orders, positions, P&L, strategy comparisons, trade journal and CSV export. Clearly label data freshness and paper vs live mode.

## Phase 10
Implement operational monitoring, backups, secrets handling, recovery drills, access controls, alerting, deployment docs and end-to-end tests. Report remaining limitations.

## Standard checkpoint prompt
Review git diff and tests. Explain what changed, what was tested, remaining risks, and exact next milestone. Update docs/PROJECT_STATUS.md and docs/CHANGELOG.md. Do not start the next phase without my approval.
