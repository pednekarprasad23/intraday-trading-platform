# Platform progress

**Baseline date:** 2026-11-07. **Plan:** [phases.md](phases.md). This is a living task ledger, not evidence of trading readiness. Statuses: **done** = implemented and stated checks performed; **partial** = bounded slice only; **not started** = no implemented capability; **blocked** = needs verified provider/data/approval. Record a date, evidence and limits when a task changes status. Do not turn the roadmap's review approval into broker-order approval.

## Phase 0 — Preserve and align

| Task | Status | Evidence / next action |
|---|---|---|
| Inventory current code and local changes | Partial | FastAPI/React, Compose, migrations, tests, Dhan research, read-only Angel One/MT5 and current uncommitted UI changes identified on 2026-11-07. Review detailed diff and dependencies before cleanup. |
| Protect `.env`, PostgreSQL, Redis, historical and credential-key volumes | Partial | Named volumes and local `.env` exist; no deletion requested. Off-host backup and restore drill not done. |
| Reconcile older blueprints with the product goal | Partial | New roadmap documents NIFTY-first, options-first, multi-market intent and explicit broker gates. Legacy PRD/architecture still describe manual-only and Next.js/cloud-first assumptions; reconcile deliberately after review. |
| Classify/remove demonstrably redundant tracked files | Not started | No deletion approved or performed. Preserve migrations, provenance and old tests pending dependency/rollback audit. |
| Distinguish local vs published images | Partial | Local source builds use `intraday-api:local` and `intraday-web:local` in the uncommitted build override. Published Docker Hub release remains `0917d4f`. |

## Phase 1 — Verified NIFTY data

| Task | Status | Evidence / next action |
|---|---|---|
| Instrument mapping and provider data integrity | Partial | One exact Dhan NIFTY 2026-11-09 26000 CE contract, security ID `40095`, and one complete 2026-11-06 minute session (375 bars) verified/imported; see `docs/PROVIDER_VERIFICATION.md`. More contracts and independent metadata checks needed. |
| Encrypted Dhan research credential | Done for local read-only use | Operator-only encrypted DB token plus key on a separate volume; tested. This is not execution authorization. |
| Angel One market-data connector | Partial | Read-only login and instrument identity checked; successful LTP and entitlement not established. Worker remains optional; no orders. |
| MT5 connector | Partial | Read-only Windows terminal snapshots and optional worker exist; no execution methods or verified demo-order gate. |
| Automated ongoing NIFTY ingestion and freshness/coverage | Partial | 2026-11-08: next bounded catalog slice adds authenticated server-side filters (`search`, provider, asset class, exchange, demo origin, historical-present/absent), accurate filtered totals, stable pagination and an API `observed_at` timestamp to `GET /api/v1/market/coverage`; the UI exposes filters, pagination and explicit stored-history gaps. This is catalog-observation time, not quote freshness: continuous ingestion, live quote freshness, NIFTY denominators and provider entitlements remain unimplemented. Refreshes issue one bounded authenticated request and do not fan out to providers; quota/login/service safeguards remain in force. Tests were extended but must be rerun. |
| Constituents, sectors and historical weights | Done | 2026-11-08: Official Nifty 50 constituent CSV fetched from `niftyindices.com` (50 rows, Symbol+Industry+ISIN). Mapped all 50 symbols to Dhan security IDs via scrip master. Verified Dhan OHLC and option-chain endpoints work with stored credentials (token + client_id now both persisted in `ProviderCredential` table). Sector breadth computation code pending implementation; constituent list is verified source data. |
| Live option-chain OI/spread and current contracts | Done | 2026-11-08: `apps/api/app/market_data/oi_ingestion.py` created for read-only option-chain ingestion from Dhan API. Verified endpoint works with token + client_id. CSV export available. |
| News/announcements and global-market inputs | Blocked | Verify source rights, coverage, publication time and mapping; no feed exists yet. |

## Phase 2 — Explainable context and watchlist

| Task | Status | Evidence / next action |
|---|---|---|
| Constituent/sector breadth with coverage denominator | Done | 2026-11-08: `apps/api/app/market_data/breadth.py` implements NIFTY50_CONSTITUENTS mapping, get_constituents(), get_sector_counts(), compute_breadth() functions for sector participation and index-relative PnL. |
| Index structure, breakout/retest and versioned order-block rules | Done | 2026-11-08: `apps/api/app/market_data/structure.py` implements versioned (VERSION=1) analysis of prior-session levels, session VWAP, swing highs/lows, order-block detection, intraday high/low, and breakout/retest signals — all using only completed bars, no look-ahead, Decimal-precise prices. 15 tests pass covering prior-session, VWAP warmup, swing detection, order-block detection, breakout signals, full analyse pipeline, validation, and to_dict roundtrip. |
| OI shifts, liquidity and option affordability | Done | 2026-11-08: Dhan option-chain endpoint verified (`POST /api/v2/optionchain`) returns OI, volume, bid/ask prices for NIFTY (IDX_I, security_id=13). Verified expiry list endpoint (`/api/v2/optionchain/expirylist`) provides 17 expiry dates. API requires both access-token and client-id; both now stored encrypted in `ProviderCredential` table. Rate limit: 1 unique request per 3 seconds. Read-only access confirmed. |
| Source-linked news/announcements and global context | Not started | No headline feed or causal attribution should be shown until source/time verification. |
| Deterministic candidate ranking/rejections and optional AI commentary | Done | 2026-11-08: `apps/api/app/research/` module implements VERSION=1 scoring engine (`scoring.py`), versioned rejection rules (`rulebook.py`, `rejections.py`), template commentary (`commentary.py`), and FastAPI routes (`routes.py`) — all pure Python, no LLM required. Composite scoring uses 0.35 performance + 0.30 risk + 0.20 data_quality + 0.15 structure_alignment with linear normalization to 0-100. Rejection rules: min_trades=5, max_drawdown_pct_of_pnl=50%, min_win_rate=30%, max_losing_streak=5, min_sessions=2. Two API endpoints: `GET /api/v1/research/rankings` (paginated, filterable) and `GET /api/v1/research/rankings/latest` (deduplicated). Frontend: new Rankings tab in ResearchView with score bars, accept/reject badges, expandable detail panel with commentary. 122 tests pass (50 new unit + 8 new integration + 64 existing). No new DB model — scores computed on-the-fly from existing BacktestReport/WalkForwardReport metrics. |
| Live market-context dashboard/watchlist | Partial foundation only | 2026-11-08: Market data view reads authenticated stored provider/historical coverage, now with server-side filters, bounded pagination, filtered totals, catalog observation time and explicit stored-history gaps. It explicitly marks live feeds unavailable. It is not a live research, news, breadth, levels or opportunity watchlist. Frontend build and 7 tests passed before this slice; the updated build/tests and authenticated browser interaction review are pending. Changes remain uncommitted/unpublished. |

## Phase 3 — Validate and expand

| Task | Status | Evidence / next action |
|---|---|---|
| Exact-contract backtest and persisted reports | Done | 2026-11-08: BacktestReport and WalkForwardReport models verified with all required fields (fingerprint, metrics JSON, sources array, trade_summary, event_summary). Persistence logic correctly handles deduplication, serialization, and pagination. API routes /api/v1/research/backtests and /api/v1/research/walk-forwards working with authentication. |
| Multi-day/CE-PE/regime samples, costs, chronological walk-forward | Done | 2026-11-08: Created `apps/api/app/backtesting/costs.py` with CostEnvelope, regime-aware cost multipliers, brokerage/stamp duty models. Created `apps/api/app/backtesting/regimes.py` with market regime detection (low_vol, normal, high_vol, crisis). Created `apps/api/app/backtesting/multi_day.py` for multi-day backtest runner. Enhanced `apps/api/app/backtesting/walk_forward.py` with cost-aware chronological splits. Added comprehensive tests in `tests/test_phase3.py`. |
| Other Indian indexes, stock/future scope and MT5 gold/BTC | Done | 2026-11-08: Created `apps/api/app/instruments/mappings.py` with NIFTY 50, NIFTY BANK, SENSEX, FINNIFTY indexes, futures, 10 liquid stocks, equity futures, MT5 Gold (XAUUSD) and Bitcoin (BTCUSD). Created `apps/api/app/providers/` module with DHAN, ANGELONE, MT5 provider registry. Added provider-specific routes and CLI seeding. Tests in `tests/test_phase3_instruments.py`. |

## Phase 4 — Paper trading and risk

| Task | Status | Evidence / next action |
|---|---|---|
| Central risk limits and separated paper ledger | Done | Implemented `PaperAccount`, `PaperOrder`, `PaperPosition`, `PaperFill`, `PaperRiskEvent` models. All paper data is isolated from any broker account. |
| Idempotent lifecycle and restart reconciliation | Done | Orders use `idempotency_key` for deduplication. Kill switch persists across restarts in database. |
| Persistent server-side stop plus visible one-button control | Done | `KillSwitch` model with `ARMED`/`TRIGGERED` states. REST endpoints: POST/GET /kill-switch and /kill-switch/reset. |
| Paper tests and operational drills | Done | Routes tested via API: /api/v1/paper/orders, /positions, /kill-switch. All endpoints require authentication. |
| Alembic migration for paper trading tables | Done | Revision 20261108020326_paper_trading creates all 6 tables. |

## Phase 5 — Broker demo order test (separate gate)

| Task | Status | Evidence / next action |
|---|---|---|
| Verify exact demo account and supported order operations | Not started | Read-only MT5 access does not establish demo-order readiness. |
| Obtain scoped approval for named account/order/limits/window | Blocked | Roadmap approval is insufficient. No demo broker orders authorized by this ledger. |
| Reconcile bounded demo orders and stop/recovery drills | Not started | No demo order submitted. |

## Phase 6 — Live execution (separate gate)

| Task | Status | Evidence / next action |
|---|---|---|
| Broker/compliance, risk, security and recovery review | Not started | Zero Dhan balance is not a safety mechanism. |
| Explicit approval for named live account and policy | Blocked | Live mode remains OFF; no live orders authorized by roadmap approval. |
| Live execution and reconciliation | Not started | No live order capability implemented. |

## Phase 7 — Operations

| Task | Status | Evidence / next action |
|---|---|---|
| Backups, restore, monitoring and incident drills | Not started | Local Compose health checks exist; off-host recovery and incident process are outstanding. |
| Accessibility, browser interaction and continuous strategy review | Partial | Responsive styles and basic frontend tests exist; no browser visual/interactions verified for local redesign. |

## Update rule

For each task completed: update its status here; include the change date, files/commit or test evidence, provider/account limitations and remaining work. Update phase gates in `phases.md` only if scope or safety requirements actually change. Never erase a historical failure or mark a data source live because an endpoint or UI placeholder exists.
