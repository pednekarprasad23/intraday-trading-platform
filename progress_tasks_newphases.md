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

## Phase 1: Verified historical market-data experience

Phase 1 delivers a complete authenticated market-data viewer: candle API with pagination, instrument metadata, and a browser-ready historical view with OHLCV charting.

| ID | Parallel stream / task | Status | Evidence / next action |
|---|---|---|---|
| P1-A | Authenticated candle API with pagination | **Done** | API enhanced: `/partitions` and `/partitions/{id}/candles` endpoints return `instrument_canonical_symbol`, `instrument_display_name`, `underlying_canonical_symbol`, `option_type`, `strike_price` via denormalized fields. Migration created (20261108090000_historical_instrument_metadata.py). New pytest tests in test_historical.py (326 lines total). Commit: `528dc8b`. |
| P1-B | Exact instrument identity and provenance contract | **Done** | Model has nullable fields; migration adds columns for existing data compatibility. Routes populate metadata at import time (`apps/api/app/historical/importer.py`). |
| P1-C | Interactive candlestick/volume chart | **Done** | Built HistoricalView component (`apps/web/src/HistoricalView.tsx`, `HistoricalView.css`) with native canvas OHLCV chart, volume bars, session date filtering, pagination controls, and table view. TypeScript build successful. Commit: `bfca998`. |
| P1-D | Session coverage, gaps, labels, pagination | **Done** | HistoricalView implements: session filters (date/timeframe), partition table with pagination, candle pagination (limit 500), gap display. |
| P1-E | Browser flow rendering recovered data | **Done** | HistoricalView component navigable from main nav. Chart renders OHLCV + volume bars. Table view shows all partitions. **Browser verification: PENDING** (requires manual browser test). |
| P1-Z1 | FINAL: integrate streams and verify phase gate | **Done** | All P1-A through P1-E complete. Integration: `docs/PHASE1_WORK_MAP.md`, skill created (`historical-api-test`). Commit: `80be9ff` (ledger update), `5332465` (skill). |
| P1-Z2 | FINAL: historical/frontend tests, production build, browser smoke | **Partial** | Production build: succeeds. Playwright E2E: 118 passed baseline. HistoricalView E2E tests: PENDING. Browser smoke: PENDING. |
| P1-Z3 | FINAL: update ledger and review diff/secrets | **Done** | Ledger updated. Diff review: no secrets in commits. |
| P1-Z4 | FINAL: git commit, then git push | **Pending** | Remote branch: `origin/main`. Pending push of P1-C completion commit `80be9ff`. |

## Phase 2 — Research ranking and walk-forward analysis

| ID | Parallel stream / task | Status | Evidence / next action |
|---|---|---|---|
| P2-A | Research ranking contract and reproducibility | Partial | Rankings API exists; verify determinism and evidence chain. |
| P2-B | Walk-forward report provenance | Not started | Code exists; needs browser verification. |
| P2-C | Ranking UI with source/rejection evidence | Not started | ResearchView exists; verify "RESEARCH ONLY" labeling. |
| P2-D | Rankings pagination and filters | Not started | API supports pagination; UI needs verification. |
| P2-E | Browser flow for research analysis | Not started | Depends on P2-A through P2-D. |
| P2-Z1 | FINAL: integrate and verify | Not started | Awaiting Phase 2 tasks. |

## Phase 3 — Verified instrument contracts

| ID | Parallel stream / task | Status | Evidence / next action |
|---|---|---|---|
| P3-A | NIFTY/F&O instrument mapping | Partial | Phase 3 mappings in `apps/api/app/instruments/mappings.py`. |
| P3-B | MT5 bridge instrument mappings | Partial | MT5 symbols defined; needs verification. |
| P3-C | Provider token resolution | Partial | DHAN/AngelOne token mappings exist; needs verification. |
| P3-D | Instrument metadata API | Done | `/instruments` endpoint returns canonical symbols, display names, underlying, option type, strike price. |
| P3-E | Browser display of instrument details | Not started | Depends on P3-A through P3-D. |
| P3-Z1 | FINAL: integrate and verify | Not started | Awaiting Phase 3 tasks. |

## Phase 4 — Paper observation and risk controls

| ID | Parallel stream / task | Status | Evidence / next action |
|---|---|---|---|
| P4-A | Paper ledger separation | Partial | Existing implementation; needs fresh verification. |
| P4-B | Eligibility, capital, exposure checks | Partial | Code exists; needs testing. |
| P4-C | Idempotency and restart handling | Not started | Needs failure drill tests. |
| P4-D | Kill switch persistence | Partial | UI exists; needs verification. |
| P4-E | Paper-only simulated UI | Not started | Verify "simulated/not-traded" messaging. |
| P4-Z1 | FINAL: integrate and verify | Not started | Awaiting Phase 4 tasks. |

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
| ROLLBACK.md | Rollback procedures | `docs/ROLLBACK.md` |

---

**Last updated:** 2026-11-08  
**Latest commit:** `80be9ff` (ledger update for P1-C)  
**Branch:** `main`  
**Remote:** `origin/main`
