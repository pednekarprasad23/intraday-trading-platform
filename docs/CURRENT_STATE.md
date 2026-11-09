# TradeCartel Current State & Handoff Summary

## A. Current Golden State
- **Branch:** `main`
- **Current HEAD SHA:** `2f0760d3e7e6b93f395f9f6dbee8e1664329cbde`
- **origin/main SHA:** `2f0760d3e7e6b93f395f9f6dbee8e1664329cbde`
- **Local == Remote:** YES
- **V2.10 Stable Tag:** `tradecartel-v2.10-stable`
- **V2.10 Tag Commit SHA:** `36c3ccf1585eb7ad3b43ef3b0c8e161b0bd99c9e` (Tag object hash: `9351de0ceb264b19f391b856164988035f5fcd63`)

---

## B. Current Product Architecture
Market Data -> Normalization -> Discovery -> Scanner -> MarketCandidate -> Analysis Engines -> Opportunity Engine -> Ranking -> Historical Replay -> Outcome Evaluation -> Missed Opportunity Analysis -> Calibration -> Opportunity Portal

---

## C. Current Analysis Engines
1. **Liquidity Quality** (bid-ask spread depth, volume consistency)
2. **Greeks Snapshot** (delta, gamma, theta, vega sanity)
3. **IV Snapshot** (implied volatility levels and skew)
4. **OI / Participation** (open interest buildup and volume activity)

---

## D. Current UI & User Acceptance
- **V2.11 Opportunity Portal** (`apps/web/src/OpportunitiesView.tsx`, `api.ts`, `main.tsx`) is fully implemented and operationally deployed.
- **Product Owner Visual Rating:** **5 / 100**
- **User Acceptance Status:** NOT ACCEPTED. The current V2.11 visual/UX implementation is rejected. Next iteration must prioritize frontend/product UX reconstruction, NOT another backend architecture rewrite.

---

## E. Current Known Limitations
- Historical technical indicators (RSI, MACD, Supertrend, ATR, VWAP, IV Rank, IV Percentile) are not yet implemented because genuine normalized historical time-series capability must be established first.

---

## F. Dhan Integration Status
- Dhan MCP / historical-data capability was discovered but intentionally **DEFERRED**.
- Do not automatically introduce Dhan MCP into production runtime.

---

## G. Execution / Paper Trading Status
- **PAPER is OUT OF THE ACTIVE ROADMAP.**
- Do not extend, repair, enhance, or reintroduce PAPER unless explicitly authorized by the user.
- Opportunity intelligence is strictly read-only and zero-execution-coupled.

---

## H. Next Product Priority
- **V2.11 UX reconstruction and refinement**.
- Primary expected editable scope: `apps/web/`.
- Preserve backend/API contracts unless a proven UI-blocking defect requires otherwise.

---

## I. User UI Expectations
- Modern, professional, enterprise-grade market intelligence terminal feel.
- Slightly larger readable typography, clean dense tables, strong hierarchy, richer controlled status colors, minimal clutter.
- Fast interpretation of rank, score, and explanation breakdown ("WHY THIS RANKED HERE").
- Zero PAPER clutter, zero BUY/SELL execution controls.

---

## J. Development Principles
- `main` is the active branch.
- Git is the durable recovery checkpoint.
- Local HEAD must match origin/main before returning control.

---

## K. Database & Zero-Touch Bootstrap Documentation
- **Infrastructure:** Docker Compose multi-service architecture (`deployment/compose/compose.yml`) provisioning PostgreSQL 16.6 and Redis 7.4.2 with persistent volumes (`postgres_data`, `redis_data`).
- **Auto-Migration:** The API container (`apps/api/Dockerfile`) automatically executes `alembic upgrade head` upon container startup before serving traffic.
- **Verified Bootstrap Command:**
  ```bash
  docker compose --env-file deployment/compose/.env -f deployment/compose/compose.yml up -d
  ```
- **Environment Configuration:** Requires a valid `.env` file (based on `.env.example`) containing database credentials (`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, etc.). A clone cannot run without configuration if environment secrets/variables are required.

---

## L. Security & Portability
- **Committed-Secret Risk:** NO (no secrets, access tokens, or private credentials committed).
- **Files Requiring Attention:** None.
