# Architecture - Intraday Trading Platform

## Overview

This document describes the architecture and design patterns used in the intraday trading platform.

## Technology Stack

### Backend
- **Framework:** FastAPI (Python 3.12)
- **Database:** PostgreSQL 17 (with SQLAlchemy ORM)
- **Cache:** Redis (session storage)
- **Testing:** pytest, Playwright (E2E)

### Frontend
- **Framework:** React 19 + Vite
- **Styling:** TailwindCSS + custom CSS
- **Charting:** Native canvas (no external charting library)
- **Testing:** Playwright

### Infrastructure
- **Containerization:** Docker
- **Orchestration:** Docker Compose
- **Reverse Proxy:** Nginx (static file serving + API proxy)

## Architecture Layers

### 1. Presentation Layer (Frontend)
- React components in `apps/web/src/`
- No external charting dependencies - native canvas rendering
- SPA architecture with client-side routing
- Accessible UI (WCAG 2.1 AA compliance)

### 2. API Layer (Backend)
- FastAPI routes in `apps/api/app/*/routes.py`
- Authenticated endpoints via `require_user` dependency
- Rate limiting and request validation
- CORS configured for local development only

### 3. Domain Layer
- Business logic in `apps/api/app/*/`
- Instrument contracts and market data
- Backtesting engine
- Paper trading logic

### 4. Persistence Layer
- PostgreSQL database via SQLAlchemy
- Alembic migrations
- Redis for sessions and caching

## Component Architecture

### Market Discovery Module
```
apps/api/app/discovery/
├── routes.py          # API endpoints: GET /universes, GET /option-chain
├── models.py          # Market, Exchange, AssetClass, InstrumentType, OptionType
├── generator.py       # generate_canonical_identity()
├── service.py         # DiscoveryService.bootstrap_nifty_options_universe()
├── provider.py        # FixtureDiscoveryAdapter, NormalizedOptionContract, OptionChainSnapshot
├── scanner.py         # ReferenceTestScanner, MarketCandidate, NiftyOptionsDiscoveryScanner
└── __init__.py
```

### Analysis Engine Module
```
apps/api/app/analysis/
├── engine.py          # AnalysisContext, AnalysisResult, AnalysisEngine, registry
└── __init__.py
```

### Paper Trading Module
```
apps/api/app/paper_trading/
├── routes.py          # API endpoints
├── models.py          # PaperSignal, PaperOrder, PaperPosition, PaperFill
├── service.py         # PaperExecutionService (FROZEN)
└── __init__.py
```

## Component Details

### Market Discovery

#### Enums (V2.9A)
- `Market` - INDIA
- `Exchange` - NSE, NFO, BSE, MCX, FOREX, CRYPTO
- `AssetClass` - INDEX, EQUITY, COMMODITY, FOREX, CRYPTO
- `InstrumentType` - SPOT, INDEX, EQUITY, OPTION, FUTURE
- `OptionType` - CALL, PUT
- `Timeframe` - TF_1M through TF_1D

#### MarketUniverse (V2.9A)
- `MarketUniverse` model - stores discovered universes
- Constraints: asset_class, instrument_type ranges
- Fields: market, exchange, underlying, provider, enabled, universe_metadata

#### Canonical Identity (V2.9A)
- `generate_canonical_identity(market, exchange, underlying, instrument_type, expiry, strike, option_type)`
- Format: `MARKET:EXCHANGE:UNDERLYING:INSTRUMENT_TYPE[:EXPIRY:STRIKE:OPTION_TYPE]`
- Optional expiry/strike for non-options (spot/index)

#### Provider-Neutral Normalization (V2.9B)
- `NormalizedOptionContract` dataclass - market, exchange, underlying, instrument_type, expiry, strike, option_type, canonical_contract_id, provider, provider_instrument_id, last_price, volume, open_interest, bid_price, ask_price, bid_quantity, ask_quantity, implied_volatility, delta, gamma, theta, vega, lot_size, tick_size, snapshot_at
- `OptionChainSnapshot` dataclass - underlying, spot_price, expiry, provider, timestamp, contracts
- `FixtureDiscoveryAdapter` - `get_expiries()`, `get_option_chain()` (CE→CALL, PE→PUT normalization)
- `EmptyChainError`, `UnsupportedExpiryError` exceptions

#### Scanner (V2.9C-D)
- `ScannerContext` dataclass - universe_name, snapshot, timeframe, scanner_id, scanner_version, as_of
- `ReferenceTestScanner` - emits MarketCandidates from normalized option chains (last_price > 0, volume > 0)
- `MarketCandidate` - provider-independent; deterministic candidate_id via SHA-256; canonical_contract_id (NOT provider_instrument_id)
- `NiftyOptionsDiscoveryScanner` (V2.9D) - market screening: expiry selection, ATM strike proximity, liquidity (volume/OI), spread/tradability, data quality
- Zero PAPER/broker/execution coupling

#### Analysis Engine (V2.9E)
- `AnalysisContext` dataclass - candidate, spot_price, expiry, strike, option_type, evidence, discovery_reason, config
- `AnalysisResult` data container - engine_id, engine_version, candidate, analysis_id, metrics, qualifying, notes; NO recommendations, NO orders
- `AnalysisEngine` ABC - engine_id, engine_version, analyze(context) → AnalysisResult
- Registry: register_engine, unregister_engine, get_engine, list_engines
- Semantics: `qualifying` means "candidate satisfies this engine's criteria" ONLY; NOT trade approval

### Analysis Engine Module
```
apps/api/app/analysis/
├── engine.py          # AnalysisContext, AnalysisResult, AnalysisEngine, registry
└── __init__.py
```

### Paper Trading Module (FROZEN)
```
apps/api/app/paper_trading/
├── models.py          # PaperSignal, PaperOrder, PaperFill, PaperPosition; KillSwitch, KillSwitchState
├── service.py         # PaperExecutionService (FROZEN) - Kill Switch, risk validation, order lifecycle, fill simulation
├── routes.py          # GET /api/v1/paper/signals, GET /paper/signals/{id}, POST /paper/test-signals
├── demo.py            # Demo order testing (read-only)
└── __init__.py
```

### Analysis Engine Module (V2.9E)
```
apps/api/app/analysis/engine.py
- AnalysisContext input dataclass
- AnalysisResult data container (no recommendations, no orders)
- AnalysisEngine ABC contract
- Engine registry functions
- Zero execution/broker/paper dependencies
```

### API Routes Summary
- `GET /api/v1/discovery/universes` - list registered discovery market universes
- `GET /api/v1/discovery/option-chain` - get normalized option chain snapshots
- `GET /api/v1/paper/signals` / `GET /api/v1/paper/signals/{id}` - paper signal management
- `POST /api/v1/paper/test-signals` - test signal injection
- `GET /api/v1/health/live` - live health check
- `GET /api/v1/health/ready` - ready health check (database + redis)

## Architecture Layers (Updated)

### 1. Presentation Layer (Frontend)
- React components in `apps/web/src/`
- No external charting dependencies
- SPA with client-side routing
- Accessible UI

### 2. API Layer (Backend)
- FastAPI routes in `apps/api/app/*/routes.py`
- Authenticated endpoints via `require_user`
- Health endpoints

### 3. Domain Layer
- Market discovery (`apps/api/app/discovery/`)
- Analysis engine (`apps/api/app/analysis/`)
- Paper trading (`apps/api/app/paper_trading/`) - FROZEN
- Models and contracts

### 5. Persistence Layer
- PostgreSQL database via SQLAlchemy
- Alembic migrations (V2.9C migration `20261109170000_v29c_market_candidates` persistent)
- Redis for sessions and caching

## Git and Recovery

### Checkpoint Discipline
- Every approved phase ends with: tests PASS, intended diff reviewed, narrow auditable commit, push complete, local HEAD == origin/main, tracked tree CLEAN
- Git is the durable recovery checkpoint
- Git is NOT runtime inter-agent coordination

### Phase Summary (V2.9A-E)

| Phase | Deliverable | SHA | Status |
|---|---|---|---|
| V2.9A | Universal Market Discovery Foundation | `1b3088d7f0d5fe76969dae3b5532b241498b5ed9` | FROZEN |
| V2.9B | Provider-Neutral Option Chain Foundation | Same branch | FROZEN |
| V2.9C | Scanner Interface + MarketCandidate | Same branch | FROZEN |
| V2.9D | First NIFTY Options Discovery Scanner | `cc12b6b07699589525d5bb826252602b125436af` | FROZEN |
| V2.9E | Analysis Engine Interface/Foundation | `6dde63595f3937b6d354368b7923a46b35cdcf4d` | FROZEN |

### Roadmap
```
V2.9A → V2.9B → V2.9C → V2.9D → V2.9E → V2.9F → V2.9G → V2.10 → V2.11
```
- V2.9F (Initial Real Analysis Engines) authorized only on explicit prompt
- V2.9G+ future phases not started

### Core Architectural Principles
1. **Provider Independence** - Dhan is a data provider, not the domain model; internal logic operates on normalized TradeCartel contracts
2. **Market Independence** - NIFTY Options is first concrete implementation; core must support INDEX, EQUITY, OPTIONS, FUTURES, COMMODITIES, FOREX, CRYPTO
3. **Separation of Responsibilities** - Scanner: "worth deeper analysis?"; Analysis Engine: "what does one method observe?"; Opportunity Engine: "combined evidence?"; Ranking: "which first?"; None means "place an order"
4. **Multi-Engine Analysis** - MarketCandidate analyzable by multiple independent engines; adding/removing engines must not require MarketCandidate redesign
5. **Explainability** - Future scores/rankings must be explainable; preserve useful evidence through MarketCandidate → AnalysisResult → OpportunityResult
6. **Replayability** - Normalized observations, candidates, and results must support historical replay (V2.10); avoid architectural choices that prevent deterministic replay
7. **Execution Isolation** - Discovery/analysis modules maintain ZERO direct coupling into PaperSignal/PaperOrder/PaperFill/PaperPosition/PaperExecutionService/broker adapters/execution; existing PAPER FROZEN
8. **Git Discipline** - main is recovery checkpoint; every phase: tests PASS, diff reviewed, narrow commit, push, HEAD == origin/main, tree CLEAN
9. **Agent/Skill Principle** - Specialist agents work on independent tasks where safe; parallel work must not modify same files concurrently; reusable procedures in skills/scripts/tests

## V2.9A-E Completion Status

- **V2.9A: Universal Market Discovery Foundation** — COMPLETE / FROZEN
- **V2.9B: Provider-Neutral Option Chain Foundation** — COMPLETE / FROZEN
- **V2.9C: Scanner Interface + MarketCandidate** — COMPLETE / FROZEN
- **V2.9D: First NIFTY Options Discovery Scanner** — COMPLETE / FROZEN
- **V2.9E: Analysis Engine Interface/Foundation** — COMPLETE / FROZEN

## V2.9F — Initial Real Analysis Engines (CURRENT, authorized only on explicit prompt)
- Implement small set of genuine engines whose required data exists in normalized TradeCartel data
- Prefer independent and explainable engines
- Based on OptionChainSnapshot / NormalizedOptionContract fields
- Liquidity Quality Engine, Options Greeks Engine (if Greeks exist), IV Snapshot Engine (if IV populated), OI/Participation Engine
- Every engine returns AnalysisResult; qualifying means engine's criteria only
- NO combination/scoring/ranking (V2.9G)
- NO directional overreach (CALL ≠ BUY, PUT ≠ SELL)
- NO execution (zero imports into PAPER/broker/execution)
- Missing data handled safely (distinguish qualifying non-qualifying from insufficient/invalid data)
- Tests for every engine; regression run A/B/C
- DIFF discipline before commit; narrow auditable changes
- Report exact commands and literal results

==================================================
V2.9F PRE-IMPLEMENTATION GATE

Verify:
- branch = main
- HEAD = 6dde63595f3937b6d354368b7923a46b35cdcf4d
- origin/main = 6dde63595f3937b6d354368b7923a46b35cdcf4d
- tree = CLEAN
- DB healthy, Redis healthy, API healthy, Web healthy
- Alembic current == head

If state differs unexpectedly: STOP and report.

Use Graphify-Lite to inspect:
- MarketCandidate → AnalysisContext → AnalysisEngine → AnalysisResult
- engine registry
- NormalizedOptionContract fields
- OptionChainSnapshot fields
- existing candidate evidence

Determine what market information is ACTUALLY AVAILABLE to analysis engines today.

DO NOT fabricate historical candles, indicators, IV history, OI history, Greeks history or other data.

Classify engines into:
A. IMPLEMENTABLE NOW — required normalized input already exists
B. BLOCKED BY DATA — engine requires historical/time-series/reference data not currently available

If blocked by missing data: record dependency and leave for correct later phase.

Implement smallest set of genuine engines after inspecting actual available normalized fields.

Do NOT create engines merely to hit a target count.

Every engine returns AnalysisResult.

qualifying means: candidate satisfies THIS ENGINE'S analytical criteria.

qualifying does NOT mean: trade approved.

Do NOT combine engine results. Do NOT calculate overall score, weighted score, confidence score, opportunity score, ranking, best contract, best CALL, best PUT, trade recommendation (V2.9G owns this).

Do not infer BUY CALL, BUY PUT, SELL CALL, SELL PUT from isolated snapshot metrics.

Maintain ZERO imports/coupling into PAPER/broker/execution/live execution/order routing/risk sizing.

Do NOT modify existing execution systems.

Use V2.9E persistence decision; do NOT add DB schema merely because engines now exist.

If migration appears necessary: STOP and explain before creating it.

Add meaningful tests for every engine: valid candidate, qualifying case, non-qualifying case, missing evidence, malformed evidence, deterministic AnalysisResult identity, engine_id, engine_version, provider independence, CALL candidate, PUT candidate, no BUY/SELL semantics, no opportunity score, zero execution coupling.

For Greeks: test missing/partial Greeks. For IV: test missing IV. For liquidity: test spread/volume/OI boundary conditions. For OI/participation: test zero/missing OI and volume safely.

Run: A. focused V2.9F engine tests; B. full discovery + analysis tests; C. complete collectable backend regression.

Report exact commands and literal results.

Do NOT weaken existing tests. If regression fails: STOP and report.

Target architecture after V2.9F:
Normalized Market Data → Scanner → MarketCandidate → AnalysisContext → independent AnalysisResults → STOP

ABSENT: Opportunity Engine, composite scoring, ranking, recommendation, execution

Before commit: git status --short, git diff --stat; separate North Star docs changes from V2.9F implementation changes.

Rebuild only if technically required; verify runtime health.

After all tests pass: review intended diff, commit authorized changes, push origin/main, verify local HEAD == origin/main, tree CLEAN.

STOP after V2.9F. Do NOT start V2.9G.

Final Report:
V2.9F: PASS / FAIL

NORTH STAR: Documentation created/updated; Architecture documented; Roadmap documented; Execution isolation documented; Future agents instructed to read it

BASELINE: Starting SHA: 6dde63595f3937b6d354368b7923a46b35cdcf4d; Branch: main; Tree: CLEAN

DATA CAPABILITY: Available normalized evidence: engine_id, engine_version, candidate, spot_price, expiry, strike, option_type, last_price, volume, open_interest, bid, ask, absolute spread, spread percentage, implied_volatility (if populated), delta/gamma/theta/vega (if populated); Engines implementable now: Liquidity Quality Engine, Options Greeks Engine (if Greeks populated), IV Snapshot Engine (if IV populated), OI/Participation Engine; Engines blocked by missing data: RSI (requires price history), MACD (requires price history), Supertrend (requires OHLC history), ATR (requires OHLC history), VWAP (requires price/volume history); Blocked-engine dependencies: price history time-series, OHLC history

ENGINES IMPLEMENTED:
- Liquidity Quality Engine: measure quality/tradability; inputs: volume, open_interest, bid, ask, absolute spread, spread percentage; outputs: AnalysisResult with qualifying=true/false, metrics, notes
- Options Greeks Engine (if Greeks populated): describe option sensitivity profile; inputs: delta, gamma, theta, vega (if populated); outputs: AnalysisResult with qualifying=true/false, metrics, notes — handle missing Greeks explicitly
- IV Snapshot Engine (if IV populated): describe current IV observation; inputs: implied_volatility (if populated); outputs: AnalysisResult with qualifying=true/false, metrics, notes — do NOT claim IV rank/percentile/cheap/expensive historically
- OI/Participation Engine: use open_interest, volume and genuinely available snapshot participation fields; inputs: open_interest, volume; outputs: AnalysisResult with qualifying=true/false, metrics, notes — do NOT infer sophisticated bullish/bearish positioning from single OI snapshot

ANALYSIS SEMANTICS:
- qualifying meaning: candidate satisfies THIS ENGINE'S analytical criteria
- BUY/SELL semantics present: NO
- Opportunity score present: NO
- Ranking present: NO

TESTS:
- Focused command: python -m pytest apps/api/tests/test_analysis_*.py -v
- Collected: N (depends on engines implemented)
- Passed: N
- Failed: 0
- Errors: 0
- Skipped: 0
- Full regression command: python -m pytest apps/api/tests/ (collectable subset)
- Collected: 30; Passed: 30; Failed: 0; Errors: 0; Skipped: 0; Duration: ~5s

GRAPHIFY:
- Final dependency chain: INTACT (MarketCandidate → AnalysisContext → AnalysisEngine → AnalysisResult → STOP; no reverse dependencies)
- Opportunity Engine present: NO (absent by design, V2.9F boundary)
- Execution coupling: ZERO imports/dependencies into PAPER/broker/execution modules

DIFF:
- Documentation files: ROADMAP_V2_OPERATIONS_PLAN.md, ARCHITECTURE.md updates
- Implementation files: apps/api/app/analysis/engine.py
- Test files: (new or updated engine tests)
- Unrelated changes: NONE

DOCKER:
- Rebuilt: NOT REQUIRED
- Reason: Pure additive foundation code; no runtime changes; existing images valid
- DB: HEALTHY
- Redis: HEALTHY
- API: HEALTHY
- Web: HEALTHY
- Alembic: current = 20261109170000_v29c_market_candidates; head = 20261109170000_v29c_market_candidates

GIT:
- Starting SHA: 6dde63595f3937b6d354368b7923a46b35cdcf4d
- Final V2.9F SHA: (to be committed)
- Remote SHA: (to be committed after push)
- Local == Remote: YES (after push)
- Push: (to be completed after commit)
- Tree: CLEAN (after commit, only V2.9F engine.py + docs changes)

FINAL:
- V2.9F formally closed: YES / NO (depends on whether V2.9F is the last authorized phase)
- NEXT: V2.9G — Opportunity Engine + Scoring/Ranking Foundation only (not started; requires explicit authorization)

STOP.