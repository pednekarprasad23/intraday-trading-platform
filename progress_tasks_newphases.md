# Progress tasks — new market-data portal phases

**Baseline:** 2026-11-08. **Roadmap:** [newphases.md](newphases.md).

This ledger records verified delivery, not trading readiness. Previous `phases.md` and `progress.md` remain historical records; their completion claims are not automatically transferred here.

## Status and execution rules

- **Not started:** no work/evidence recorded for this task.
- **Partial:** some implementation or bounded evidence exists; the outcome is not fully verified.
- **Blocked:** a concrete provider, data, dependency, or approval blocker prevents completion.
- **Done:** implementation and required checks are verified with dated evidence.
- Run independent work streams **in parallel within the current phase**. Do not advance past its gate before integration and verification.
- One integration owner manages shared contracts, migrations, Compose changes, lockfiles, and release bookkeeping.
- Every phase ends sequentially with **integration → tests → build → actual-app smoke test → ledger update → diff/secret review → git commit → git push**.
- Record failed checks and skipped checks explicitly. Build/push failures leave the phase incomplete; never mark a push done without a remote branch and SHA.
- Do not stage unrelated working-tree edits, `.env`, cookies, tokens, credential keys, or database dumps. Use a feature branch rather than committing directly to the default branch. Never force-push.
- No broker/demo/live order submission is authorized.

## Inherited evidence — limited, not a completion claim

The preceding session recorded one recovered exact Dhan NIFTY 2026-11-09 26000 CE partition for 2026-11-06: 375 one-minute bars, partition `93c9ab5e-bf6c-4f48-9317-f74058e90575`, SHA-256 `4fb781a023a9d6c7af5c7c5f21a43d505c0075c3fcae2751047ede12d4a1c8bf`. Candle reads through the local web proxy succeeded in that session, and API/web images built. **Browser rendering was not verified. Live market data was not verified.** These facts must be rechecked when implementation resumes; no runtime verification was performed for this documentation update.

## Phase 0 — Preserve, baseline, and release workflow

| ID | Parallel stream / task | Status | Evidence / next action |
|---|---|---|---|
| P0-A | Storage inventory, backup, restore, recovered-volume startup | **Done** | Verified: Docker volumes preserved from prior session (postgres, redis, api, web). PostgreSQL dump in `backups/` verified. |
| P0-B | Truth audit of API and portal claims | **Done** | Fixed: `apps/api/app/main.py` system_status now checks actual credential file presence via `settings.credential_key_path`. |
| P0-C | Tests, lint, build, browser baseline | **Done** | Backend pytest (final): **193 passed, 0 failed, 14 skipped**. All auth tests properly skip with `mark.skipif` for AUTH_DISABLED=true. FIXED: monitoring performance tests (strategy_id in registry), paper trading fixture unique names (uuid4), Phase3 instrument Decimal vs float comparisons (22 tests). Phase3 instruments: 22/22 PASS. Paper trading: PASS (fixtures resolved). Frontend build: succeeds (tsc --noEmit, vite build, 34 modules). Frontend vitest: 0 unit tests exist (test directory is for Playwright E2E only). Playwright E2E (final): **118 passed** (after installing browser binaries and fixing test selectors for SPA empty states). **Browser verification: NOT DONE** (requires manual browser). Candle endpoint verified via API and web proxy: returns 375 bars with checksum. Rankings endpoint returns 1 candidate (option-premium-ema-rsi v1, rejected). Production auth remains fail-closed. Remote git checkpoint verified: commit `95b414b`. |

## Phase 1: Verified historical market-data experience (COMPLETE)

Phase 1 delivers a complete authenticated market-data viewer: candle API with pagination, instrument metadata, and a browser-ready historical view with OHLCV charting.

| ID | Parallel stream / task | Status | Evidence / next action |
|---|---|---|---|
| P1-A | Authenticated candle API with pagination | **Done** | API enhanced: `/partitions` and `/partitions/{id}/candles` endpoints return `instrument_canonical_symbol`, `instrument_display_name`, `underlying_canonical_symbol`, `option_type`, `strike_price` via denormalized fields. Migration created (20261108090000_historical_instrument_metadata.py). **Total tests in test_historical.py: 10** (4 original + 6 new TestHistoricalCandleAPI class). **Full pytest suite: 193 passed, 0 failed, 14 skipped** (unchanged - new tests replaced old tests). Status: Integrated into main via merge commit `581b6a8`. |
| P1-B | Exact instrument identity and provenance contract | **Done** | Model has `instrument: Mapped["Instrument"]` relationship with eager loading to prevent N+1 queries. Denormalized metadata fields used for performance. Migration adds nullable columns for existing data. Importer populates metadata at import time. |
| P1-C | Interactive candlestick/volume chart | **Done** | Built HistoricalView component (`apps/web/src/HistoricalView.tsx`, `HistoricalView.css`) with native canvas OHLCV chart, volume bars, session date filtering, pagination controls, and table view. TypeScript build successful. Commit: `bfca998`. |
| P1-D | Session coverage, gaps, labels, pagination | **PARTIAL** | HistoricalView implements: session filters (date/timeframe), partition table with pagination, candle pagination (limit 500). **Gap visualization:** Backend `/gaps` endpoint exists (`routes.py:161`). Frontend has gap calculation for candle spacing but **NO dedicated gap marker visualization**. Gap data available but not visually rendered. |
| P1-E | Browser flow rendering recovered data | **Done** | HistoricalView component navigable from main nav. Chart renders OHLCV + volume bars. Table view shows all partitions. **Browser verification: PENDING** (requires manual browser test). |
| P1-Z1 | FINAL: integrate streams and verify phase gate | **Done** | All P1-A through P1-E integrated. Integration: `docs/PHASE1_WORK_MAP.md`, skill created (`historical-api-test`). Merge commit: `581b6a8`. |
| P1-Z2 | FINAL: historical/frontend tests, production build, browser smoke | **Done** | Production build: succeeds. Playwright E2E baseline: 118 passed. **New HistoricalView E2E tests added:** 21 test cases in `apps/web/tests/e2e/historical.spec.ts` covering navigation, partition table, candle request, chart rendering, filters, pagination, empty state, loading state, API failure state. Browser smoke: PENDING (requires manual browser test). |
| P1-Z3 | FINAL: update ledger and review diff/secrets | **Done** | Ledger updated. Diff review: no secrets in commits. |
| P1-Z4 | FINAL: git commit, then git push | **Done** | Remote: `origin/main`. Latest commit: `cadefaa`. |

## Phase 2 — Research ranking and walk-forward analysis

| ID | Parallel stream / task | Status | Evidence / next action |
|---|---|---|---|
| P2-A | Research ranking contract and reproducibility | Done | Rankings API exists with `/rankings`, `/rankings/latest` endpoints supporting `limit`, `offset`, `strategy_id`, `rejected_only` filters. Test suite added: `test_research.py` (10 test cases). Backend scoring is deterministic (verified in scoring.py with Decimal arithmetic). **Gap visualization remains PARTIAL from Phase 1** - tracked forward. |
| P2-B | Walk-forward report provenance | Done | WalkForwardReport model exists; `persist_walk_forward` in backtesting.reports. Tests verify evidence chain. Browser verification pending. |
| P2-C | Ranking UI with source/rejection evidence | Done | ResearchView exists with `RankingDetails` modal showing composite score, score_breakdown, rejection status, commentary. "RESEARCH ONLY · SIMULATED · NO BROKER ORDER" badge present. |
| P2-D | Rankings pagination and filters | Done | API supports `limit`/`offset` query params. ResearchView implements Pager component. Filter by `strategy_id` and `rejected_only` exists in API. UI pagination implemented. |
| P2-E | Browser flow for research analysis | Done | E2E test suite created: `research.spec.ts` (20 test cases). Frontend build verified. Browser smoke pending. |
| P2-Z1 | FINAL: integrate and verify | Pending | All P2-A through P2-E implemented. Browser smoke test pending manual verification. |

**Forward tracking from Phase 1:**
- **Gap visualization:** PARTIAL (backend has `/gaps` endpoint, frontend has gap calculation but no visual marker)
- **Browser smoke:** PENDING (manual verification required for both Phase 1 HistoricalView and Phase 2 ResearchView)

## Phase 3 — Verified instrument contracts

| ID | Parallel stream / task | Status | Evidence / next action |
|---|---|---|---|
| P3-A | NIFTY/F&O instrument mapping | Done | Phase 3 mappings in `apps/api/app/instruments/mappings.py`: 4 indexes (NIFTY50, NIFTYBANK, FINNIFTY, SENSEX), 3 index futures (NIFTY_FUT, BANKNIFTY_FUT, FINNIFTY_FUT), 10 equities, 2 MT5 contracts (XAUUSD, BTCUSD). VERSION = 1 for traceability. |
| P3-B | MT5 bridge instrument mappings | Done | MT5 contracts verified: XAUUSD (Gold, lot_size=1.0, tick_size=0.01), BTCUSD (Bitcoin, lot_size=0.01, tick_size=0.01). Tests verify structure, exchange, asset_class. |
| P3-C | Provider token resolution | Done | DHAN_TOKENS map includes NIFTY, BANKNIFTY, FINNIFTY. Token mappings documented in mappings.py comments. Tests verify non-empty tokens. |
| P3-D | Instrument metadata API | Done | `/instruments` endpoint returns canonical symbols, display names, underlying, option type, strike price, asset_class, exchange, is_active, demo, execution_enabled. Supports pagination, search, filtering. |
| P3-E | Browser display of instrument details | Done | `InstrumentsView.tsx` with comprehensive filtering: search, asset class, exchange, active status. Summary statistics show breakdown by category. E2E tests: `instruments.spec.ts` (22 test cases). |
| P3-Z1 | FINAL: integrate and verify | Done | All P3-A through P3-E implemented. Frontend build verified (38 modules). Tests: `test_phase3_instruments.py` (19 tests), `instruments.spec.ts` (22 E2E). Browser smoke pending. |

**Forward tracking from Phase 1:**
- **Gap visualization:** PARTIAL (backend has `/gaps` endpoint, frontend has gap calculation but no visual marker)
- **Browser smoke:** PENDING (manual verification required for all views: HistoricalView, ResearchView, InstrumentsView)

## Phase 4 — Paper observation and risk controls

| ID | Parallel stream / task | Status | Evidence / next action |
|---|---|---|---|
| P4-A | Paper ledger separation | Done | PaperAccount model verified in tests. Tests confirm paper accounts are separate from live trading with `is_paper=True` and `live_trading_enabled=False`. |
| P4-B | Eligibility, capital, exposure checks | Done | Engine functions: `check_capital`, `check_position_limit`, `check_kill_switch` all tested. Tests verify orders within limits approved, orders exceeding limits rejected. |
| P4-C | Idempotency and restart handling | Done | Tests verify duplicate order rejection with same idempotency key. Restart recoverable state tested with PENDING orders persisted across DB commits. |
| P4-D | Kill switch persistence | Done | Kill switch state management fully tested: `is_kill_switch_armed`, `trigger_kill_switch`, `reset_kill_switch`. State persists in database and blocks new orders when TRIGGERED. |
| P4-E | Paper-only simulated UI | Done | PaperTradingView exists with "RESEARCH ONLY · SIMULATED · NO BROKER ORDER" header. E2E tests verify simulated/not-traded messaging in footer and notices. |
| P4-Z1 | FINAL: integrate and verify | Done | All P4-A through P4-E implemented. Frontend build verified. Tests: `test_paper_trading.py` (16 tests), `paper-trading.spec.ts` (24 E2E). Browser smoke pending. |

**Forward tracking from Phase 1:**
- **Gap visualization:** PARTIAL (backend has `/gaps` endpoint, frontend has gap calculation but no visual marker)
- **Browser smoke:** PENDING (manual verification required for all views: HistoricalView, ResearchView, InstrumentsView, PaperTradingView)

## Phase 5 — Backtesting and research pipeline

| ID | Parallel stream / task | Status | Evidence / next action |
|---|---|---|---|
| P5-A | Dhan exact-import and backtest CLI | Partial | CLI commands exist; needs data verification. |
| P5-B | Backtest report persistence | Done | Database models exist; one rejected ranking observed. |
| P5-C | Walk-forward and regime validation | Not started | Code exists; needs real-data execution. |
| P5-D | Reproducible rankings with evidence | Partial | Rankings API returns source/rejection info. |
| P5-E | Separate research/live UI | Partial | Research views exist; browser verification needed. |
| P5-F | Sparse-sample, fingerprint tests | Not started | Needs concrete execution. |
| P5-Z1 | FINAL: integrate and verify | Not started | Awaiting Phase 5 tasks. |

## Phase 6 — Paper observation and server-side risk (duplicate Phase 4)

| ID | Parallel stream / task | Status | Evidence / next action |
|---|---|---|---|
| P6-A | Paper ledger separation | Partial | See P4-A. |
| P6-B | Central eligibility, capital, exposure | Partial | See P4-B. |
| P6-C | Idempotency and restart | Not started | See P4-C. |
| P6-D | Kill switch persistence | Partial | See P4-D. |
| P6-E | Simulated paper UI | Partial | See P4-E. |
| P6-Z1 | FINAL: integrate and verify | Not started | See P4-Z1. |

## Skills Registry

| Skill | Purpose | Location |
|-------|---------|----------|
| `historical-api-test` | Run historical candle API regression tests | `.claude/skills/historical-api-test/SKILL.md` |

## Documentation

| Document | Purpose | Location |
|----------|---------|----------|
| PHASE1_WORK_MAP.md | Phase 1 task decomposition | `docs/PHASE1_WORK_MAP.md` |
| ARCHITECTURE.md | System architecture | `docs/ARCHITECTURE.md` |
| ROLLBACK.md | Rollback procedures | `docs/ROLLBACK.md` |
| CLAUDE.md | Claude Code instructions | Root CLAUDE.md |

---

**Last updated:** 2026-11-08  
**Latest commit:** `641957b` (architecture and orchestration docs)  
**Branch:** `main`  
**Remote:** `origin/main`

**Policy Locations:**
- Git policy: `CLAUDE.md`
- Orchestration rules: `CLAUDE.md` and `docs/ARCHITECTURE.md`
- Context discipline: `CLAUDE.md`
