# TradeCartel-Inspired Roadmap V2: Trading Operations & Control Dashboard

**Status:** APPROVED MASTER PLAN  
**Permanent Scope Exclusion:** Harvey / sales automation is permanently removed from all plans, phases, and architectures.

---

## Important Roadmap Directives & Corrections

1. **No Database Migrations in V2.1:** Database migrations, `projects` tables, `project_id` foreign keys, and lifecycle schema changes are deferred to later phases (V2.3–V2.5) after their requirements are proven.
2. **Honest Operational Status Labels:** Broker integrations are primarily read-only while paper/simulated execution is available. The platform uses honest operational labels based on actual backend state:
   - `PAPER`
   - `BROKER READ-ONLY`
   - `PAUSED`
   - `OFFLINE`
   Generic "LIVE" is strictly avoided unless the backend contract actually supports live broker order routing.
3. **Kill Switch Visibility:** V2.1 displays current server-side kill-switch status. Kill-switch behavior and reset protocols are preserved without redesign or scope creep.
4. **Test Reporting Integrity:** All test reports must reflect the literal pytest and Playwright summaries from the actual runtime environment.

---

## 1. Product Goal

The primary objective of Roadmap V2 is to deliver a professional, TradeCartel-inspired **Trading Operations & Control Dashboard** built directly on the platform's existing core engines (paper trading ledger, order execution lifecycle, persistent kill switch, signal engine, market snapshot adapters, and research/backtesting store).

Instead of an abstract academic quant suite, V2 delivers an operator-centric cockpit providing high-visibility command and control:
* **Real-time visibility** into operational projects (e.g. *Daily XAU*, *XAUUSD Pullback*, *NIFTY F&O*), broker connectivity, and execution states.
* **Deterministic lifecycle tracking** from Signal Ingestion $\to$ Routing $\to$ Broker Transmission $\to$ Acceptance/Rejection $\to$ Fill $\to$ Position $\to$ Exit $\to$ Settlement.
* **Full Reconciliation & Auditing** across signals, simulated broker orders, fills, and realized P&L.
* **Operational Risk Controls** with prominent `PAPER` / `PAUSED` / `BROKER READ-ONLY` toggles, persistent server-side kill switches, exposure limits, and audit trails without dangerous hair-trigger shortcuts.
* **Honest Execution Classification** distinguishing between `PAPER` (isolated simulation ledger), `BROKER READ-ONLY` (read-only connector telemetry), and `RESEARCH ONLY` (offline partition analysis) without false claims or fake state transitions.

---

## 2. Current Capability Matrix

Based on actual repository code analysis across `apps/api/app/`, `apps/web/src/`, `services/`, and database models:

| Capability | Existing Status | Evidence / Location in Repository | V2 Operational Gap |
| :--- | :--- | :--- | :--- |
| **Command Dashboard** | **PARTIAL** | `apps/web/src/main.tsx` (simple nav + status widget); `apps/api/app/monitoring/routes.py` (`/monitoring/health`) | No unified cockpit; lack of aggregated KPIs (Today's P&L, active projects, signals, rejected orders) and recent activity stream |
| **Projects / Strategies** | **PARTIAL** | `apps/api/app/models.py` (`StrategyVersion`, `StrategySignal`); `app/monitoring/performance.py` (`STRATEGY_REGISTRY`, `register_strategy`); `app/strategies/contracts.py` | Projects are not modeled as top-level operational entities with broker associations, run state, and runtime metrics |
| **Signals** | **EXISTS** | `apps/api/app/market_data/dhan.py` (`/dhan/signals`, EMA/RSI/Volume); `app/models.py` (`StrategySignal`, `ResearchEvaluation`) | Signals are isolated in provider endpoints; no unified query endpoint across strategies/projects with execution correlation |
| **Orders** | **EXISTS** | `apps/api/app/paper_trading/models.py` (`PaperOrder`, `PaperOrderState`); `app/paper_trading/routes.py` (`GET /paper/orders`, `POST /paper/orders`) | Order view lacks rich filtering (by project, date, instrument) and detailed lifecycle visual breakdown |
| **Positions** | **EXISTS** | `apps/api/app/paper_trading/models.py` (`PaperPosition`); `app/paper_trading/routes.py` (`GET /paper/positions`); `app/market_data/mt5.py` (terminal positions) | Positions table lacks mark-to-market live P&L recalculation against current quotes and project-level grouping |
| **Trades / Fills** | **EXISTS** | `apps/api/app/paper_trading/models.py` (`PaperFill`); `app/market_data/mt5.py` (`Deal`); `app/backtesting/reports.py` (trade summaries) | No dedicated `/paper/trades` query route aggregating closed trades and historical fills with realized P&L |
| **P&L Tracking** | **EXISTS** | `apps/api/app/paper_trading/models.py` (`PaperAccount.unrealized_pnl`, `realized_pnl`); `app/paper_trading/routes.py` (`/paper/summary`) | Summary provides aggregate account P&L, but lacks daily historical P&L breakdown and per-project P&L attribution |
| **Reconciliation** | **PARTIAL** | `apps/api/app/paper_trading/models.py` (`PaperOrder.fills`, `PaperOrder.strategy_id`, `idempotency_key`); `test_backtesting.py` | No unified reconciliation view matching signal $\to$ paper order $\to$ fill $\to$ position $\to$ exit state |
| **Operational State** | **PARTIAL** | `apps/api/app/paper_trading/models.py` (`KillSwitch`, `PaperAccount.is_active`); `app/monitoring/performance.py` (`StrategyStatus`) | Broker-level status (blocking new entries while preserving signal intake and position monitoring) is not explicitly state-managed per project |
| **Paper Trading** | **COMPLETE** | `apps/api/app/paper_trading/` (`engine.py`, `models.py`, `routes.py`, `demo.py`); `apps/web/src/PaperTradingView.tsx` | UI is a basic tabbed panel; lacks professional high-visibility status indicators and execution correlation |
| **Live Broker Architecture**| **PARTIAL (Read-Only)** | `services/mt5_bridge/` (read-only terminal bridge); `services/angelone_worker/` (read-only snapshot worker); `app/providers/angelone/readonly.py` | Order execution via live broker APIs is strictly disabled (`orders_available: Literal[False]`); live connectivity is read-only telemetry |
| **Operational Risk** | **EXISTS** | `apps/api/app/paper_trading/models.py` (`PaperRiskEvent`, `max_daily_loss`, `max_total_exposure`); `app/paper_trading/routes.py` (`/paper/risk-events`) | Risk limits are enforced in paper engine, but lack dashboard-level risk KPI gauges and active exposure tracking |
| **Kill Switch** | **COMPLETE** | `apps/api/app/paper_trading/models.py` (`KillSwitch`, `KillSwitchState`: ARMED, TRIGGERED, RESET_PENDING); `app/paper_trading/routes.py` | Fully functional server-side persistent kill switch with deliberate confirmation text (`RESET`) |
| **Market Data** | **COMPLETE** | `apps/api/app/market_data/` (`dhan.py`, `mt5.py`, `angelone.py`, `coverage.py`); `apps/web/src/CoverageView.tsx`, `Mt5View.tsx`, `AngelOneView.tsx` | Functioning connector snapshots with freshness indicators; need consolidation into global dashboard status bar |
| **Historical Data** | **COMPLETE** | `apps/api/app/historical/` (`routes.py`, `reader.py`, `importer.py`); `apps/web/src/HistoricalView.tsx` | Complete parquet partition management and candlestick inspection; ready to serve as operational reference |
| **Backtesting Engine** | **COMPLETE** | `apps/api/app/backtesting/` (`engine.py`, `reports.py`, `routes.py`, `costs.py`); `test_backtesting.py` | Fully validated with exact-contract persistence and transaction costs; ready for operational strategy verification |
| **Walk-Forward Analysis** | **COMPLETE** | `apps/api/app/backtesting/walk_forward.py`; `apps/api/app/models.py` (`WalkForwardReport`) | Slicing and cross-validation functional; available in research tab |
| **Research Rankings** | **COMPLETE** | `apps/api/app/research/` (`routes.py`, `scoring.py`, `rulebook.py`); `apps/web/src/ResearchView.tsx` | Fully functional candidate ranking and rulebook verification; operational |
| **Production Auth** | **COMPLETE** | `apps/api/app/auth.py` (`User`, session cookies, Argon2 password hasher, Redis session store) | Production fail-closed auth with development localhost override (`AUTH_DISABLED=true`) |
| **System Health** | **COMPLETE** | `apps/api/app/monitoring/routes.py` (`/monitoring/health`, `/monitoring/metrics`, `/monitoring/backups`) | Health and operational metrics ready for global dashboard integration |
| **Audit Logs** | **EXISTS** | `apps/api/app/models.py` (`AuditLog`); `app/auth.py` (logs login/logout events); `app/paper_trading/models.py` (`PaperRiskEvent`) | Audit logs exist in DB but lack an operator-facing viewer and unified event stream |
| **User/Role Management**| **PARTIAL** | `apps/api/app/models.py` (`User`); `app/auth.py` (`/auth/me`, `/auth/login`, `/auth/logout`) | Single user model; no multi-role permissions (sufficient for current single-operator workspace) |

---

## 3. Core V2 vs Optional Future Enhancements

### Core V2 Scope (Market Discovery + Analysis Foundation)
1. **Market Discovery Pipeline:** V2.9A-V2.9E complete — foundation, provider-neutral option chain, scanner, analysis engine contract
2. **Analysis Engine Framework:** V2.9E — abstract contract, context/result types, registry; zero execution coupling
3. **Opportunity Engine + Scoring/Ranking:** V2.9G (future) — combine independent engine results, deterministic ranking, explainability
4. **Historical Replay + Missed Opportunity Analysis:** V2.10 (future) — replay normalized observations, candidates, engine results; answer "what did TradeCartel know"
5. **Opportunity Portal:** V2.11 (future) — operator-facing portal for ranked opportunities, explainable scores, historical analysis

### Optional Future Backlog (Demoted from Core V2+)
* Multi-asset Options Surface / 3D Volatility Smile fitting.
* Exotic Greeks calculation engine (Vanna, Charm).
* Barone-Adesi-Whaley American options pricing.
* Exchange SPAN margin replication and multi-asset portfolio covariance matrices.
* Portfolio Value-at-Risk (VaR) and Expected Shortfall (ES).
* Historical macro stress-testing matrices (COVID 2020, 2008 Crash).
* Institutional order-book liquidity matching and square-root market impact models.
* Massive 10,000-row virtualized data grids.
* Live automated broker order execution (requires formal regulatory compliance, live capital authorization, and exchange certifications).
* V2.10 historical replay infrastructure.
* V2.11 Opportunity Portal UI.

---

## 4. Information Architecture

The V2 workspace navigation now includes market discovery and analysis:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ TOPBAR: Brand │ Status Pill │ Market/Session │ Mode: PAPER SIMULATION │ Kill Switch │
├───────────────┬────────────────────────────────────────────────────────────────────────┤
│ SIDEBAR       │ MAIN CONTENT AREA                                                      │
│               │                                                                        │
│ MARKET DISCOVERY   │ 1. MARKET DISCOVERY      (V2.9A-E pipelines; scanner; candidates) │
│ • Discovery      │ 2. ANALYSIS              (V2.9E contract; independent engines)          │
│   Pipeline       │ 3. CANDIDATES            (MarketCandidate; persists in DB)            │
│ • Scanner        │ 4. ANALYSIS CONTEXT      (AnalysisContext piped from candidates)        │
│ • Candidates     │ 5. ANALYSIS ENGINES      (independent engines → AnalysisResult)           │
│                │ 6. ANALYSIS RESULTS      (qualifying means engine's criteria only)          │
│                │ 7. OPPORTUNITY ENGINE    (V2.9G; combine + rank; NOT YET)                │
│                │ 8. HISTORICAL REPLAY     (V2.10; replay candidates+engine results)          │
│                │ 9. OPPORTUNITY PORTAL    (V2.11; operator-facing; NOT YET)                │
│                │ 10. RESEARCH & DATA      (Historical candlesticks, backtests, rankings)      │
│                │ 11. SYSTEM HEALTH        (Service health, dependencies, audit logs)          │
│                │                                                                        │
│ FOUNDATION       │                                                                        │
│                │                                                                        │
└───────────────┴────────────────────────────────────────────────────────────────────────┘
```

---

## 17. Final Phase Order

```
V2.1 → V2.2 → V2.3 → V2.4 → V2.5 → V2.6 → V2.7 → V2.8 → V2.9A → V2.9B → V2.9C → V2.9D → V2.9E → V2.9F → V2.9G → V2.10 → V2.11
```

---

## 18. V2.9A-E COMPLETION STATUS

- **V2.9A: Universal Market Discovery Foundation** — COMPLETE / FROZEN
- **V2.9B: Provider-Neutral Option Chain Foundation** — COMPLETE / FROZEN
- **V2.9C: Scanner Interface + MarketCandidate** — COMPLETE / FROZEN
- **V2.9D: First NIFTY Options Discovery Scanner** — COMPLETE / FROZEN
- **V2.9E: Analysis Engine Interface/Foundation** — COMPLETE / FROZEN
- **V2.9F: Initial Real Analysis Engines** — CURRENT (authorized only on explicit prompt)
- **V2.9G: Opportunity Engine + Scoring/Ranking** — FUTURE
- **V2.10: Historical Replay + Missed Opportunity Analysis** — FUTURE
- **V2.11: Opportunity Portal** — FUTURE

---

## 4. Information Architecture

The revised V2 workspace navigation replaces the generic menu with an operator-first operational hierarchy:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ TOPBAR: Brand │ Status Pill │ Market/Session │ Mode: PAPER/BROKER READ-ONLY │ Kill Switch │
├───────────────┬────────────────────────────────────────────────────────────────────────┤
│ SIDEBAR       │ MAIN CONTENT AREA                                                      │
│               │                                                                        │
│ OPERATIONAL   │ 1. COMMAND DASHBOARD  (Global KPIs, Project Cards, Real-time Activity) │
│ • Dashboard   │ 2. PROJECTS           (Strategy & Account Operations, Controls)        │
│ • Orders      │ 3. ORDERS & SIGNALS   (Signal Stream, Execution Lifecycle, Order Log)  │
│ • Positions   │ 4. POSITIONS & TRADES (Open Exposures, Closed Trades, Realized P&L)    │
│ • Reconcile   │ 5. RECONCILIATION     (Signal-to-Fill Audit, Discrepancy Filter)       │
│ • Risk        │ 6. RISK & CONTROLS    (Kill Switch, Loss Limits, Exposure Gauges)      │
│               │                                                                        │
│ FOUNDATION    │ 7. RESEARCH & DATA    (Historical Candlesticks, Backtests, Rankings)   │
│ • Research    │ 8. SYSTEM HEALTH      (Service Health, Dependencies, Audit Logs)       │
│ • System      │                                                                        │
└───────────────┴────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Command Dashboard Specification

### A. Global Status Bar
* **System Health:** Aggregate operational state (`HEALTHY`, `DEGRADED`, `OFFLINE`) derived from `/api/v1/monitoring/health`.
* **Broker Connectivity:** Read-only telemetry status for connected providers (`DHAN: CONNECTED`, `MT5: TERMINAL OK`, `ANGELONE: SNAPSHOT OK`).
* **Trading Mode Badge:** Prominent, honest badge (`PAPER SIMULATION` or `BROKER READ-ONLY`).
* **Kill Switch Status:** High-visibility pill (`ARMED` in emerald/muted blue, `TRIGGERED` in crimson, `RESET PENDING` in amber).
* **Clock & Session:** UTC and Market Session time (IST / Forex market session indicator).

### B. Summary KPIs (Stat Tiles)
* **Today's P&L:** Net daily return with currency indicator and color-coded trajectory.
* **Realized P&L:** Closed trade profit/loss for the active session.
* **Open P&L:** Mark-to-market unrealized profit/loss across open positions.
* **Active Positions:** Count of open legs and total market exposure value.
* **Active Projects:** Operational project count (e.g., 3 active: *Daily XAU*, *XAUUSD Pullback*, *NIFTY F&O*).
* **Signals Today:** Total trading signals ingested across all configured strategies.
* **Rejected / Blocked Orders:** Count of orders intercepted by risk limits or rejected by the engine.

### C. Project Operational Cards
Each project card displays:
* **Identity:** Project Name, Strategy ID, Target Instrument, Primary Broker/Connector.
* **State Badges:** Project State (`ACTIVE`, `STOPPED`, `TESTING`), Execution Mode (`PAPER`, `PAUSED`, `BROKER READ-ONLY`).
* **Latest Action:** Last signal direction/timestamp, last execution state, last fill price.
* **Position & Return:** Current open units, unrealized P&L, today's realized P&L.
* **Health & Alerts:** Operational status (`OK`, `WARNING`, `ERROR`), active risk events.

### D. Recent Activity Stream
* Chronological consolidated event stream showing the latest 20 events: Signals received, Orders submitted, Fills executed, Exits triggered, and Risk events blocked.

---

## 6. Project Operations & Management

The platform supports a generalized project architecture instantiated with real strategy pipelines:
1. **Daily XAU:** Gold daily breakout strategy targeting `XAUUSD` via MT5 terminal / Dhan commodities.
2. **XAUUSD Pullback:** Intraday momentum pullback strategy on `XAUUSD` 5-minute partitions.
3. **NIFTY F&O:** Indian index intraday momentum strategy on `NIFTY` index and options contracts via Dhan / Angel One.

### Project Operational Controls
* **State Toggles:**
  * `ACTIVE`: Normal operating state. Incoming signals are eligible for simulated order routing.
  * `PAUSED`: Protective state. Blocks NEW order creation while preserving continuous signal intake, recording, and active position management.
  * `STOP`: Inactivates the project; cancels pending orders.
  * `TEST / DEMO`: Routes execution exclusively to the demo simulation engine (`/api/v1/demo`).
* **Operational Rule:** State transitions require operator confirmation; the frontend never fakes backend state transitions. All states are validated against backend models.

---

## 7. Signal, Order & Execution Lifecycle

### Lifecycle Visual Pipeline
For every trade intent, the operator can track the discrete stage:

```
[1. SIGNAL RECEIVED] ──► [2. ROUTED] ──► [3. BROKER SENT] ──► [4. BROKER ACCEPTED / DENIED]
                                                                        │
┌───────────────────────────────────────────────────────────────────────┘
▼
[5. FILLED / PARTIAL] ──► [6. POSITION OPEN] ──► [7. EXIT SIGNAL / SENT] ──► [8. CLOSED]
```

### Backend Capability Mapping
* **1. Signal Received:** `EXISTS` (`StrategySignal` in `app/models.py`, `/dhan/signals`).
* **2. Routed:** `PARTIAL` (`PaperTradingEngine.submit_order` validates instrument and risk).
* **3. Broker Sent:** `EXISTS` (Recorded as `submitted_at` on `PaperOrder`).
* **4. Broker Accepted / Denied:** `EXISTS` (`PaperOrderState.SUBMITTED` vs `PaperOrderState.REJECTED` with `PaperRiskEvent`).
* **5. Filled / Part Filled:** `EXISTS` (`PaperOrderState.FILLED`, `PARTIAL`, with linked `PaperFill` records).
* **6. Position Open:** `EXISTS` (`PaperPosition` updated atomically with fill quantities).
* **7. Exit Signal / Exit Sent:** `PARTIAL` (Exit orders submitted as offsetting paper orders with `strategy_id`).
* **8. Closed:** `EXISTS` (`PaperPosition.quantity == 0`, realized P&L settled to `PaperAccount`).

---

## 8. Positions, Trades & P&L Operations

### First-Class Operating Screens
1. **Positions View:** Instrument Symbol, Project / Strategy ID, Side (`LONG`/`SHORT`), Quantity, Average Entry Price, Current Price (from latest quote snapshot), Unrealized P&L, Realized P&L, Last Marked Timestamp.
2. **Orders View:** Order ID, Creation Time, Project / Strategy ID, Instrument, Side (`BUY`/`SELL`), Order Type (`MARKET`, `LIMIT`, `STOP`), Quantity, Filled Quantity, Execution Price, Status Badge, Rejection Reason.
3. **Trades / Fills View:** Fill ID, Order ID, Execution Time, Project, Instrument, Side, Fill Quantity, Fill Price, Commission, Slippage, Realized P&L, Execution Provenance (`PAPER_SIM`).

---

## 9. Reconciliation Engine & Console

* **Audit Table:** End-to-end trace joining:
  * `Signal Timestamp` & `Direction` (`StrategySignal`)
  * `Strategy ID` & `Project Name`
  * `Simulated Order ID` & `Requested Quantity` (`PaperOrder`)
  * `Broker Response State` (`SUBMITTED`, `FILLED`, `REJECTED`)
  * `Execution Fill Price` & `Filled Quantity` (`PaperFill`)
  * `Resulting Position State` (`PaperPosition`)
  * `Exit Order State` & `Realized P&L`
  * `Discrepancy / Error Flag` (e.g. signal generated but order rejected, fill quantity mismatch).
* **Filtering & Export:** Filter by Discrepancies Only, Project, Date, or Instrument; CSV/JSON audit export for compliance records.

---

## 10. Operational Risk & Kill-Switch Controls

* **Persistent Kill Switch:** Server-side SQLite/Postgres backed kill switch (`KillSwitch` model). When triggered:
  * Blocks all new paper/simulated orders across all projects.
  * Cancels all pending/submitted limit and stop orders.
  * Prevents any reset until deliberate two-step confirmation (typing `RESET` in confirmation dialog).
* **Max Daily Loss Guard:** Enforces session drawdown limits; automatically triggers a `daily_loss_limit` risk event upon breach.
* **Max Total Exposure Guard:** Restricts aggregate portfolio margin/exposure across open positions.
* **Key Safety Principle:** Consequential trading actions (kill switch trigger, position liquidation, PAUSE toggle) **must require deliberate mouse clicks and confirmation dialogs**. No hair-trigger keyboard shortcuts will be bound to destructive actions.

---

## 11. Research, Backtesting & Market Data Integration

The existing, validated research modules are integrated as operational tools rather than an isolated subsystem:
* **Historical Partition Viewer:** Inspect candle data, data freshness, and gap statistics (`HistoricalView.tsx`).
* **Strategy Backtest Runner:** Run and review deterministic backtests with transaction costs, slippage, and multi-day regimes (`ResearchView.tsx`).
* **Walk-Forward Validation:** Review out-of-sample stability folds before promoting a strategy to `ACTIVE` operational state.
* **Market Telemetry:** Real-time visibility into Dhan, MT5, and Angel One connector snapshots (`Mt5View.tsx`, `AngelOneView.tsx`, `CoverageView.tsx`).

---

## 12. System Health, Audit Telemetry & Settings

* **Health Overview:** Live dependency checks (`database`, `redis`, `api`) with response time in ms (`/api/v1/monitoring/health`).
* **Audit Trail:** Operator activity log (`AuditLog`) capturing login, logout, strategy state changes, and kill-switch activations.
* **Risk Events Stream:** Queryable log of every blocked order or risk violation (`PaperRiskEvent`).
* **Database Backups:** List and status of automated database backup snapshots (`/api/v1/monitoring/backups`).

---

## 13. UI System & 21st.dev Strategy

We leverage 21st.dev component patterns to produce a modern, polished dark-mode operations cockpit without blindly imitating an illegible, cramped terminal:

### Design Tokens & Aesthetics
* **Typography:** Clean, slightly larger readable fonts (Inter / SF Pro with JetBrains Mono for numbers and tickers).
* **Color Hierarchy:**
  * Backgrounds: Deep slate/zinc canvas (`#0b0f17`, `#111827`) with subtle borders (`#1f2937`).
  * Text: High-contrast primary (`#f9fafb`), secondary muted (`#9ca3af`).
  * P&L Trajectory: Vibrant emerald (`#10b981` / `#059669`) for profit; distinct coral/rose (`#f43f5e` / `#e11d48`) for loss.
  * Status Indicators: High-clarity badges for `PAPER` (blue), `PAUSED` (amber), `TRIGGERED` (crimson), `BROKER READ-ONLY` (teal).
* **21st.dev Component Selection:**
  * KPI Stat Cards with trend indicators and sparklines.
  * Interactive Project Overview Cards with segmented status badges.
  * Filterable Data Tables with sortable columns, pagination, and empty/loading states.
  * Modal Confirmation Dialogs for kill-switch activation and position closure.
  * Segmented Control Tabs for seamless view switching.

---

## 14. Data Refresh Strategy

* **Initial Architecture: Polling / Controlled Refresh (No WebSockets initially):**
  * Dashboard KPIs and Status Bar: 10-second background polling with manual "Refresh" button.
  * Open Positions and Orders: 5-second polling when viewing the active trading screens.
  * Activity Stream and Audit Logs: 15-second polling.
* **Rationale:** The existing FastAPI REST architecture provides sub-50ms response times for database and memory queries. Polling avoids WebSocket reconnection edge cases, state synchronization bugs, and proxy/firewall complexity.
* **WebSocket / SSE Consideration:** Retained in future backlog; to be introduced only if high-frequency tick streaming becomes a validated operational requirement.

---

## 15. API & Database Gap Matrix

| Area | Existing Endpoint / Model | Required V2 Gap / Enhancement | Migration Required? |
| :--- | :--- | :--- | :--- |
| **Dashboard** | `/monitoring/health`, `/paper/summary` | `GET /api/v1/dashboard/summary` (consolidating KPIs, active projects count, today's signals, and risk status into a single call) | No (aggregates existing models) |
| **Projects** | `StrategyVersion` model, `STRATEGY_REGISTRY` | `Project` model or expanded `StrategyProject` entity with `broker_state` (`PAPER`/`PAUSED`/`BROKER READ-ONLY`), runtime status (`ACTIVE`/`STOPPED`), and linked instrument | In Phase V2.5 (Alembic migration for `projects` table) |
| **Orders** | `GET /paper/orders`, `PaperOrder` | Add `project_id` and `lifecycle_state` fields to `PaperOrder`; add date/instrument filters to `GET /paper/orders` | In Phase V2.3 (Alembic migration for `paper_orders` columns) |
| **Positions** | `GET /paper/positions`, `PaperPosition` | Add `project_id` link to `PaperPosition`; return current mark price from quotes cache | In Phase V2.4 (Alembic migration for `paper_positions.project_id`) |
| **Trades** | `PaperFill` model | `GET /api/v1/paper/trades` endpoint returning enriched trade executions with realized P&L and project filters | No (new query route on existing `paper_fills`) |
| **Reconcile** | `StrategySignal`, `PaperOrder`, `PaperFill` | `GET /api/v1/reconciliation` endpoint joining signals to orders, fills, and position states with discrepancy flags | No (new query route on existing models) |
| **Audit** | `AuditLog` model in DB | `GET /api/v1/monitoring/audit-logs` endpoint for operator visibility | No (expose existing `AuditLog` table) |

---

## 16. Detailed V2 Implementation Phases

### Phase V2.1: UI Foundation, Navigation Shell & Common Operator Status Components
* **Objective:** Establish the modern dark-themed operational shell, topbar status bar, view routing, and shared 21st.dev design tokens without database or backend changes.
* **User-visible result:** The application loads with a polished dark-mode navigation sidebar, global status bar (system health, broker connection badges, honest `PAPER SIMULATION` badge, and persistent kill switch indicator), and view switcher without regressions to existing views.
* **What exists:** `apps/web/src/main.tsx`, `api.ts`, `style.css`.
* **What is missing:** Modern dark design tokens, global topbar status aggregator, responsive operator shell.
* **Frontend work:** Implement `AppShell.tsx`, `GlobalStatusBar.tsx`, `StatusBadge.tsx`, update CSS tokens in `style.css`.
* **Backend work:** None (consumes existing `/monitoring/health`, `/paper/kill-switch`, `/auth/me`).
* **Database/migration work:** None (explicitly prohibited in V2.1).
* **Graphify impact checks:** Check callers of `apps/web/src/main.tsx` and `api.ts`.
* **21st.dev candidates:** Modern dark application shell, status badges, segmented nav buttons.
* **Specialist agent ownership:** FRONTEND AGENT.
* **Focused tests:** Component tests for `GlobalStatusBar` and `StatusBadge`.
* **Backend regression requirement:** Full backend test suite passing (253 tests, 0 failures, 0 errors).
* **Playwright tests:** `smoke.spec.ts` updating selectors; view switching validation.
* **Acceptance criteria:** Application loads cleanly, displaying live status bar and responsive navigation with 0 console errors.
* **Git checkpoint:** `feat(web): implement modern operational shell and global status bar`.
* **Docker rebuild requirement:** Web container rebuild / hot-reload after push.
* **Risk/rollback notes:** Pure frontend change; rollback via git revert.

### Phase V2.2: Command Dashboard & Project Operational Cards
* **Objective:** Build the main Command Dashboard view with summary KPI cards, active project operational cards, and recent activity feed.
* **User-visible result:** An operator opens the dashboard and immediately sees: Today's P&L, Realized/Open P&L, Active Projects, Kill Switch status, project cards for *Daily XAU*, *XAUUSD Pullback*, and *NIFTY F&O*, and a chronological activity stream.
* **Database/migration work:** None (aggregates existing tables).

### Phase V2.3: Signals, Orders & Execution Lifecycle Console
* **Objective:** Deliver a first-class Orders & Signals operations screen with full execution lifecycle tracking.
* **Database/migration work:** Add `lifecycle_state` index / column if proven necessary.

### Phase V2.4: Positions, Trades & Reconciliation Console
* **Objective:** Build dedicated operating views for active Positions, closed Trades history, and the end-to-end Reconciliation Console.
* **Database/migration work:** None.

### Phase V2.5: Project Controls & Operational Risk Management
* **Objective:** Implement project-level operational controls (`ACTIVE` / `PAUSED`), exposure risk gauges, and persistent kill-switch management.
* **Database/migration work:** Alembic migration for `projects` table.

### Phase V2.6: Research, Backtesting & Market Historical Integration
* **Objective:** Harmonize the validated research, backtesting, and market telemetry views into the new operational workspace.
* **Database/migration work:** None.

### Phase V2.7: System Health, Monitoring & Audit Telemetry
* **Objective:** Expose comprehensive operational telemetry: system health, database connection metrics, automated backup status, and operator audit trail.
* **Database/migration work:** None.

### Phase V2.8: Hardening, Responsive Polish & Release Validation Gate
* **Objective:** Complete end-to-end operational hardening, mobile/desktop responsive optimization, cross-browser compatibility, and final release validation.
* **Database/migration work:** None.

---

## 17. Final Phase Order

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│   V2.1   │ ──► │   V2.2   │ ──► │   V2.3   │ ──► │   V2.4   │
│ UI Shell │     │ Command  │     │ Orders & │     │Positions │
│ & Status │     │Dashboard │     │Signals   │     │& Reconcil│
└──────────┘     └──────────┘     └──────────┘     └──────────┘
      │                                                  │
      ▼                                                  ▼
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│   V2.5   │ ──► │   V2.6   │ ──► │   V2.7   │ ──► │   V2.8   │
│ Project  │     │ Research │     │ System   │     │Hardening │
│ Controls │     │ Integrate│     │ & Audit  │     │& Release │
└──────────┘     └──────────┘     └──────────┘     └──────────┘
```
