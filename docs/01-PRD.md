# Product Requirements Document (PRD)
## AI-Assisted Intraday Trading Intelligence Platform

**Version:** 1.0  
**Status:** Baseline for implementation  
**Initial user model:** Single user  
**Primary interface:** Responsive web application

## 1. Product vision

Build a personal trading intelligence platform that continuously collects authorised market data, evaluates instruments using deterministic quantitative strategies, ranks potential intraday opportunities, uses an LLM to investigate shortlisted candidates, and presents trade proposals for explicit manual approval.

The product is a research and decision-support system first. It is not an autonomous trading bot. No LLM output may directly submit, modify, or cancel a live order.

## 2. Confirmed product decisions

| Area | Decision |
|---|---|
| Hosting | Cloud |
| AI inference | Salad Cloud Qwen endpoint, behind a provider abstraction |
| Historical data | Broker data plus independent provider(s) |
| Users | Single user initially; avoid blocking future multi-user support |
| UI | Responsive web and mobile browser |
| Trading style | Intraday |
| Opportunity types | Options buying/selling, futures and eligible cash instruments |
| Markets | NIFTY, BANKNIFTY, SENSEX, FINNIFTY, Gold and BTC |
| Broker integrations | Angel One SmartAPI and MetaTrader 5 |
| Execution | Manual approval; paper mode before live mode |
| Packaging | Docker Compose for initial deployment |
| Source control | Git repository; secrets excluded |

Instrument availability, market-data permissions, broker product types, contract specifications and live execution eligibility must be verified per provider. Do not assume every instrument can be traded through both brokers.

## 3. Goals

1. Provide one watchlist and dashboard for the selected markets.
2. Collect and normalise live and historical market data from multiple sources.
3. Detect and rank intraday setups using reproducible rules.
4. Analyse derivatives data where available, including OI, IV, Greeks, liquidity and expiry.
5. Ask Qwen to review only shortlisted candidates and return structured research.
6. Provide transparent evidence, counter-evidence, data freshness and risk information.
7. Support historical backtesting and live paper trading.
8. Support manually approved orders through separate broker adapters.
9. Record signals, research, approvals, orders, fills and outcomes for audit and learning.
10. Keep early infrastructure and operating costs minimal.

## 4. Non-goals for version 1

- Autonomous or unattended live trading.
- High-frequency or latency-sensitive trading.
- Claims that AI can predict prices or guarantee profitable trades.
- Reinforcement learning or custom predictive ML before reliable data and baselines exist.
- Public SaaS, subscriptions or multi-tenant billing.
- Copy trading or sharing broker credentials.
- Unrestricted redistribution of exchange data.
- Kubernetes, service mesh or distributed microservices.
- A production-grade mobile native app.

## 5. User journeys

### 5.1 Start-of-session
1. User signs in.
2. Dashboard displays market calendar/session status and feed health.
3. Data connectors authenticate and report their status.
4. Instrument master and contract metadata are refreshed.
5. User sees which instruments are eligible for scanning and which feeds are stale or unavailable.

### 5.2 Opportunity discovery
1. Market-data worker receives ticks or candles.
2. Normalisation and validation layer checks timestamps, duplicates, gaps and source.
3. Candle builder updates configured intervals.
4. Indicator and strategy engines evaluate eligible instruments.
5. Hard filters reject stale, illiquid, invalid or out-of-session candidates.
6. Remaining candidates are ranked and stored.
7. Top candidates are queued for AI research subject to rate and cost limits.

### 5.3 Review a candidate
1. User opens a candidate.
2. UI displays underlying chart, timeframe, strategy, entry zone, invalidation, target scenarios, liquidity, spread, data timestamp and source.
3. UI displays supporting and contradicting evidence.
4. AI report is shown with model/provider/version and input snapshot reference.
5. User can mark watch, reject, or request a refreshed analysis.
6. A candidate is not an order and does not imply an execution recommendation.

### 5.4 Paper execution
1. User selects a candidate and contract.
2. Risk engine validates account configuration and proposed quantity.
3. Order preview shows side, order type, limit/trigger price, quantity, estimated exposure and costs.
4. User confirms.
5. Paper broker simulates order lifecycle, including partial fill/rejection scenarios where supported.
6. Positions and P&L are updated from simulated fills.

### 5.5 Live execution (later release)
1. Live mode is disabled by default.
2. User must explicitly enable it after completing broker onboarding and compliance checks.
3. User reviews a final order ticket and confirms each order.
4. Server-side risk checks are repeated immediately before submission.
5. Broker response and subsequent order/trade updates are reconciled.
6. Uncertain submission outcomes are treated as unknown and reconciled before retrying; never blindly resubmit.

## 6. Functional requirements

Priority definitions: **P0** required for the first usable release; **P1** next; **P2** later.

### 6.1 Identity, security and settings
- P0: Single-user login with secure password hashing and session expiry.
- P0: Secrets supplied through secret manager/environment, never committed to source.
- P0: Audit security-sensitive actions.
- P1: TOTP/MFA, device/session management and recovery workflow.
- P1: Separate paper/live environment configuration.
- P2: Multi-user roles and permissions.

### 6.2 Instrument master
- P0: Canonical internal instrument ID independent of broker token.
- P0: Store exchange, segment, symbol, underlying, asset class, expiry, strike, option type, lot size, tick size, multiplier and trading status where applicable.
- P0: Map each canonical instrument to one or more provider-specific identifiers.
- P0: Track metadata source and last-verified timestamp.
- P0: Do not hardcode changing tokens, lot sizes or expiry schedules.
- P1: Automated contract-master import and change detection.

### 6.3 Market data
- P0: Connector interface for streaming and historical data.
- P0: Normalise timestamps to UTC internally; render exchange/broker local time in UI.
- P0: Store source, received time, event time and quality status.
- P0: Detect stale feeds, duplicates, out-of-order events and data gaps.
- P0: Build 1m, 3m, 5m, 15m, 30m and 1h candles from authorised data; daily context may be imported.
- P0: Persist historical candles and support idempotent imports.
- P1: Tick archive and replay, subject to storage and provider permissions.
- P1: Independent historical provider adapter.
- P1: Data reconciliation between sources; do not silently merge inconsistent feeds.

### 6.4 Analysis
- P0: EMA, RSI, MACD, ATR, Bollinger Bands, VWAP, ADX and relative volume.
- P0: Basic price structure: swing highs/lows, range, breakout and retest.
- P0: Strategy definitions are versioned and parameterised.
- P0: Every signal records the exact input candle/data snapshot and strategy version.
- P1: Options chain, OI/change in OI, PCR, IV, Greeks, spread and liquidity metrics when source data supports them.
- P1: Market regime and cross-timeframe alignment.
- P2: Additional strategies and statistical/ML research.

### 6.5 Scanner and ranking
- P0: Configurable instrument universe and scan intervals.
- P0: Candidate generation is deterministic and reproducible.
- P0: Hard rejection rules for stale data, invalid contracts, inadequate liquidity, excessive spread, out-of-session data and risk restrictions.
- P0: Store rejected candidates/reasons where useful for analysis.
- P0: Rank candidates with versioned score components; score is not a probability of profit.
- P0: Deduplicate repeated signals and track candidate lifecycle.
- P1: User-configurable watchlists and strategy weights.
- P1: Alerts for new/high-priority candidates.

### 6.6 AI research
- P0: Provider abstraction; Salad Qwen is initial provider.
- P0: Send structured, bounded research payloads only for shortlisted candidates.
- P0: Request schema-constrained JSON response.
- P0: Validate response; store model, prompt version, input reference, output, latency and token/cost metadata if available.
- P0: Display supporting evidence, counter-evidence, missing data and risks.
- P0: AI output cannot change risk limits or place orders.
- P0: Handle timeout, malformed output, rate limit and provider outage gracefully.
- P1: Re-analysis and model comparison.
- P1: Cost budget, caching and per-candidate research throttling.

### 6.7 Backtesting and paper trading
- P0: Candle-based backtest for initial underlying strategies.
- P0: Include brokerage, taxes/fees where applicable, spread and slippage assumptions as configurable inputs.
- P0: Avoid look-ahead bias and use only information available at decision time.
- P0: Report trades, net P&L, expectancy, profit factor, drawdown, win rate and losing streaks.
- P0: Paper order lifecycle and position ledger.
- P1: Contract-level historical options backtest using actual historical contracts and premiums.
- P1: Market replay using captured events.
- P1: Walk-forward and out-of-sample testing.

### 6.8 Risk and execution
- P0: Paper mode is default.
- P0: Central risk service validates all orders regardless of UI.
- P0: Configurable max order value, quantity, open positions, daily loss and per-trade risk.
- P0: Duplicate submission protection and idempotency keys.
- P0: Order state machine and reconciliation.
- P0: Kill switch blocks new orders and exposes safe handling of existing orders/positions.
- P0: Explicit manual confirmation for every live order.
- P1: Angel One and MT5 adapters after paper workflow is proven.
- P1: Broker-specific static IP, API onboarding, tagging, rate and regulatory requirements validated before live use.

## 7. Non-functional requirements

- Reliability: one connector failure must not crash the application or unrelated connectors.
- Data integrity: immutable raw event record where retained; derived records trace to source.
- Security: TLS in transit, encrypted secrets, least privilege, no secrets in logs.
- Auditability: all approvals, risk decisions, order requests and broker responses timestamped.
- Observability: structured logs, health endpoints, feed lag, queue depth and worker heartbeat.
- Performance: dashboard updates should be near-real-time subject to provider feed and network constraints; do not promise exchange-grade latency.
- Recovery: automated database backups and documented restore test.
- Portability: Dockerised services and provider abstractions.
- Cost: no continuously running GPU requirement; AI called on demand.

## 8. Acceptance criteria for first release

1. User can sign in and view service/feed health.
2. Instrument master can be imported and provider mappings validated.
3. At least one authorised market feed can be connected without hardcoding credentials.
4. Normalised candles are persisted and visible on charts.
5. At least two deterministic strategies generate reproducible signals.
6. Candidate detail shows strategy version, timestamp, data source and rejection/quality flags.
7. Qwen can analyse a candidate and return validated structured JSON; outage does not stop scanner.
8. Paper order can be approved, simulated, filled/rejected and reconciled.
9. Risk limits reject invalid paper orders.
10. Automated tests cover normalisation, strategy calculations, risk checks and order idempotency.

## 9. Risks and dependencies

- Market-data entitlements, rate limits, history depth and redistribution rights differ by provider.
- Historical options data is not equivalent to historical index candles; contract-level history is required for credible options backtests.
- Angel One and MT5 have different contract identifiers, order semantics, sessions and execution constraints.
- MT5 Python integration normally requires a running terminal and compatible Windows environment; plan a Windows bridge.
- Broker API rules, static-IP requirements and applicable exchange/SEBI standards must be checked before live trading.
- Cloud region, fixed egress IP, data residency and broker connectivity need confirmation.
- LLM analysis may be inconsistent or wrong; treat it as commentary, not a trading authority.

## 10. Release strategy

- R0: Foundation and synthetic/demo data.
- R1: One market feed and charts.
- R2: Deterministic scanner.
- R3: AI research.
- R4: Backtesting and paper trading.
- R5: Additional instruments and independent historical source.
- R6: Broker adapters and controlled live manual execution, only after compliance and operational gates.
