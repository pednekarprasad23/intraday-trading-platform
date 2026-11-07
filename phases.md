# Platform phases

**Planning baseline:** 2026-11-07. **Status:** proposed roadmap for review, not a claim that all capabilities exist. Track individual work and evidence in [progress.md](progress.md). This roadmap supersedes the *sequence* in older blueprints where they disagree; older documents remain historical references until deliberately reconciled. NIFTY is the first validation market, not the platform's limit.

## Product outcome and boundaries

Build a continuously refreshed, evidence-backed intraday research portal that can eventually take trades on the user's behalf through a controlled, auditable execution system. Prioritize **options** and affordability (actual contract, current lot size, premium/margin, spread, maximum loss and available capital). Keep instrument and analysis contracts extensible to futures and stocks. Expand from NIFTY to BANKNIFTY, FINNIFTY, SENSEX and eligible indexes; retain separate MT5 market support for gold and BTC if the terminal/account actually offers the relevant instruments. Market availability, contract mapping and permissions are verified per provider, not assumed.

Research should connect index structure and levels with constituent/sector breadth, derivatives positioning (OI/change in OI when licensed and available), dated company announcements/news, and relevant global market context. A positive signal in one dimension is not a predicted move. Every candidate must expose supporting and opposing evidence, source and event/receipt time, data gaps, invalidation, risk, and why it was shortlisted or rejected. No fabricated quotes, headlines, order blocks, fills or performance. Define order blocks and breakouts with versioned, testable rules rather than copying another site's markings. The public order-block.com site is a UX/research reference, **not** a validated signal source or execution specification.

**Current safety boundary:** Dhan is a read-only historical research source. Angel One and MT5 are read-only integrations today; the MT5 terminal may be a demo account, but its account identity and permissions must be verified before any order test. A zero Dhan balance is not an execution guard. Live trading stays OFF by default. An approval of this roadmap authorizes research/implementation work through the non-live phases, **not** an unspecified broker order, account activation, or unattended live trading. Paper/demo and live execution each have the explicit gates below. AI may comment on evidence but must never directly place or modify an order.

## Phase 0 — Preserve and align the foundation

**Outcome:** a documented baseline and safe migration path, with no loss of research records or credentials.

- Inventory tracked code, existing Compose services, migrations, named volumes and current uncommitted UI work. Preserve `.env`, database, historical partitions and credential-key volumes; design and verify backups and recovery before schema/data changes.
- Reconcile older blueprint assumptions (Next.js/cloud-first, manual-only execution, synthetic-only fixtures) with the implemented React/Vite local stack and the new long-term automation goal. Maintain a decision log rather than silently rewriting past results.
- Classify files as active, historical reference, or demonstrably redundant. **No existing tracked files are approved for deletion by this plan.** Propose removals with dependencies, migration/rollback and diff review after proving they are unused; do not remove old migrations or provenance/test fixtures just because a newer feature exists.
- Distinguish locally built UI images from published immutable release images; never overwrite a published tag with a local build. Confirm tests/CI and secrets hygiene before publication.

**Gate:** repeatable local stack, migration/restore strategy, reviewed baseline and no accidental order path.

## Phase 1 — Verified NIFTY data and provider coverage

**Outcome:** reliable ongoing read-only observation, not a static collection of manually created reports.

- Verify current NIFTY underlying, constituents, sector memberships/weights and historical membership changes from licensed sources; record as-of dates and coverage denominators. Build a provider-neutral market universe so additional indexes and asset classes can reuse it.
- Verify Dhan/Angel One entitlements, API limits, contract masters, current options lot/tick/expiry, underlying price units, timestamps and session calendar. Distinguish exact option contracts from ATM-relative rolling observations. Expand exact-contract historical sampling across CE/PE, dates, expiries and regimes.
- Implement scheduled, bounded, idempotent market-data workers with recovery/backoff, immutable or auditable provenance, freshness/gap alerts and independent connector health. Fetch only what the account and source rights allow; do not equate a worker heartbeat with a fresh market event. Dashboard refreshes must not silently truncate a catalog: APIs use bounded pages with accurate totals, server-side filters and stable ordering; the UI exposes pagination/filter state and labels the observed-at time, source freshness, unavailable entitlements and coverage gaps. Page size and refresh behavior must remain compatible with provider quotas, login protections and service safeguards; pagination must not trigger an unbounded provider fetch.
- Evaluate authorized sources for live underlying/constituent candles, options-chain OI and change in OI, quotes/spreads, global indices and timestamped news/exchange filings. Implement each as separately typed evidence; show unavailable until verified. Respect licensing/redistribution and source latency.

**Gate:** real NIFTY coverage and freshness shown with denominators and explicit missing/stale data; every available catalog result is reachable through bounded pagination and filters without implying that stored history is a fresh quote; no fabricated enrichment or execution.

## Phase 2 — Explainable market context and options watchlist

**Outcome:** a continuously updated NIFTY view explaining what matters, not a prediction dressed as a dashboard.

- Compute constituent and sector breadth (positive/negative/unchanged, weights and participation), index trend and relevant global context from synchronized, time-stamped inputs. Flag partial universes and out-of-hours observations.
- Calculate versioned levels: prior-session range, intraday highs/lows, VWAP, swing zones, breakout/retest and precisely defined order-block candidates. Show level formation, invalidation and counter-evidence; test no-look-ahead behavior.
- Analyze option-chain OI/change in OI, liquidity, spread and contract eligibility only where authoritative data exists. Do not infer an exact tradable contract from a rolling/relative strike series.
- Ingest licensed news and corporate/exchange announcements with entity mapping, publication vs discovery time, deduplication, source link and relevance checks. Never present a headline or global move as causal proof of a NIFTY move.
- Produce deterministic candidate and rejection records with version, provenance, score components, estimated option capital/risk, uncertainty and freshness. Optional bounded AI research may summarize evidence/counter-evidence but cannot alter risk decisions or submit orders.
- Extend the portal with a real market-context timeline, watchlist, candidate detail and stale/absent states. Update by approved polling or authenticated push, without inventing market data.

**Gate:** reproducible candidate explanation and rejection reasons on verified inputs, with tests for stale/partial/conflicting sources.

## Phase 3 — Research validation and expansion

**Outcome:** evidence for deciding whether rules merit paper observation.

- Backtest on actual matched underlying/option-contract histories with completed-bar decisions, next-available entry, documented costs/spread/slippage, liquidity assumptions and adverse intrabar ambiguity. Vary costs and sample multiple dates/regimes; use chronological out-of-sample and walk-forward checks, with null metrics when undefined.
- Compare shortlisted versus rejected candidates, measure false positives and data outages; do not promote a one-day result to profitability evidence. Publish evidence, limitations and a rollback decision for each strategy version.
- Expand the same provider-neutral contracts to other eligible Indian indexes, then futures/stocks as research scope warrants; verify exchange rules, constituent history and options liquidity independently per market. For MT5 gold/BTC, keep account/symbol/timezone/unit/multiplier and data lineage separate from Indian exchange data.

**Gate:** adequate coverage and documented limits for the intended strategy; no transition to execution justified by a sparse sample.

## Phase 4 — Paper trading and server-side risk

**Outcome:** end-to-end simulated order lifecycle without a real broker order.

- Separate paper credentials, database records and account views from any broker account. Implement central server-side risk checks on every intent: instrument eligibility, actual lot/tick, quantity/value, max loss, exposure, positions, daily loss, session/time and stale-data blocks.
- Add immutable intent/order events, idempotency keys, explicit states (including uncertain), startup reconciliation, partial/rejected fill simulation and auditable candidate-to-order attribution. No AI-originated order command.
- Implement a **persistent server-side kill switch** that defaults to blocking new submissions after restart or loss of control; expose a prominent authenticated one-button stop in the UI with confirmation of state. Define separately how existing orders/positions are reconciled or cancelled; a stop cannot reverse an accepted fill. Exercise concurrency, restart, network and failure cases.
- Run bounded paper sessions and compare modeled versus observed market behavior. Document drawdown, false triggers, stop effectiveness and operational drills.

**Gate:** reviewed risk limits, tests and stop/recovery drills. Paper-mode implementation does not authorize broker submission.

## Phase 5 — Optional broker demo execution (separate order-test gate)

**Outcome:** only if approved for a named **verified demo account**, exercise the broker lifecycle with tiny bounded orders and no live-account fallback.

- Independently verify terminal/account is demo, exact symbol and volume rules, allowed order operations, credentials and environment separation. Implement account allowlists, hard quantity/exposure limits, central risk and kill switch, unique idempotency and broker-side reconciliation before the first request.
- Present the exact account, instrument, side, quantity, worst-case risk and test window for a separate explicit order-test approval. Never treat a zero-balance Dhan account as safe or use it for exploratory order pushes.
- Observe acknowledgements, partial fills, cancellations, uncertain responses and restart reconciliation; stop and report if account identity or state is ambiguous.

**Gate:** explicit, scoped demo-order authorization and verified controls. This phase is not automatically unlocked by approving this roadmap.

## Phase 6 — Controlled live execution (separate live-activation gate)

**Outcome:** consider production execution only after independently verified readiness; no live order is currently authorized.

- Review current broker/exchange/SEBI requirements, API eligibility, static egress, auditability, data rights, credential handling, backups, monitoring and recovery. Verify per-account trading permissions and exact contract mapping.
- Keep live credentials/accounts isolated and mode OFF by default. Require explicit operator activation and per-order authorization unless an independently reviewed automation policy with defined limits receives separate approval. Never infer permission from available balance or a prior demo test.
- Enforce central pre-trade risk checks, persistent kill switch, idempotency, immutable lifecycle, unknown-outcome reconciliation, alerts and human escalation; drill emergency stop and outstanding-order handling.

**Gate:** separate explicit approval for the named live account, policy and limits after evidence review. Approval of the phase plan is **not** this gate.

## Phase 7 — Operations and iterative improvement

Automate backup/restore drills, provenance retention, feed/worker health, incident response, dependency and image scanning, accessibility and browser testing, and versioned strategy monitoring. Reassess markets and providers only when entitlements and observed data support expansion. Keep [progress.md](progress.md) updated at every completed task with evidence, test results, blockers and next steps; never mark a planned feature done merely because its UI shell exists.
