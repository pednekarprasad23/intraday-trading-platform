# New product phases — visible market-data portal

**Planning baseline:** 2026-11-08. **Reference:** TheTradeCartel is a functional/UX reference only; do not copy its branding, proprietary content, signals, or visual identity. **Primary outcome:** opening the local portal must show clearly labeled, timestamped market data and usable charts. Research reports are a separate capability and are not a substitute for market data.

## Working model for every phase

- Work streams listed under **Parallel tasks** may run concurrently when they do not edit the same contract or migration.
- Each stream must return changed files, tests, evidence, limitations, and unresolved blockers before integration.
- Shared API schemas, database migrations, generated lockfiles, Compose files, and release documentation are integrated by one owner to avoid conflicting edits.
- The **Final stage** of every phase is sequential and mandatory: integrate → test → build → browser/API smoke test → update `progress_tasks_newphases.md` → review the diff and secrets → commit → push.
- A phase is not complete merely because its UI exists. Market data must be provider-derived or persisted with provenance; unavailable data stays visibly unavailable.
- Never run `docker compose down --volumes`, prune preserved storage, expose credentials to the browser, or fabricate quotes, option-chain values, news, Greeks, fills, or performance.
- No demo or live broker order is authorized by this plan.

## Phase 0 — Preserve, baseline, and release workflow

**Outcome:** a recoverable development baseline and a repeatable phase delivery process.

### Parallel tasks

1. **Storage and recovery:** inventory Compose projects, images, named volumes, database migrations, credential-key storage, and historical Parquet partitions; verify non-destructive backups and a restore drill.
2. **Current-state truth audit:** reconcile API, database, and portal claims for live, delayed, historical, simulated, and unavailable data.
3. **Quality baseline:** record backend tests, frontend tests/build, browser smoke coverage, lint status, and known failures without hiding them.
4. **Release safety:** define branch/commit naming, protected secret checks, rollback instructions, and the exact Compose files needed to mount recovered volumes.

### Gate

The preserved historical partition and credential key remain recoverable; the stack can be rebuilt without deleting data; no screen falsely claims a live feed.

### Final stage — build, commit, and push

- Merge parallel results and resolve documentation/configuration conflicts.
- Run Compose config validation, backend baseline tests, frontend tests, and production builds.
- Smoke-test health and authenticated API paths through the web proxy.
- Update `progress_tasks_newphases.md` with exact evidence and blockers.
- Review `git diff`, `git status`, tracked secrets, and generated files.
- Commit the phase milestone and push the phase branch to the configured remote. Do not force-push.

## Phase 1 — Verified historical market-data experience

**Outcome:** the operator can visibly inspect real persisted OHLCV history in the portal, not only database metadata or a raw API response.

### Parallel tasks

1. **Historical API contract:** harden authenticated partition/candle endpoints with checksum, schema, row-count, sequence, pagination, and bounded date/instrument/timeframe filters.
2. **Instrument identity:** join each partition to display name, canonical symbol, exact contract identity, expiry, strike, option type, provider key, and source provenance.
3. **Chart experience:** add an interactive intraday candlestick/volume view with instrument, session, timeframe, and pagination controls plus a table view for accessibility.
4. **Coverage experience:** show available sessions, missing sessions, bar counts, checksum/provenance, import receipt time, and explicit historical—not live—labels.
5. **Verification:** add API tests, integrity-failure tests, frontend tests, and a browser flow that selects the recovered partition and visibly renders its 375 bars.

### Gate

The portal visibly renders the checksum-verified 2026-11-06 exact NIFTY option session, identifies all 375 one-minute bars, and never labels it live or current.

### Final stage — build, commit, and push

- Integrate the API, types, chart, table, filters, and tests.
- Run historical/backend tests, frontend tests, accessibility checks, and production API/web image builds.
- Launch the real stack with recovered volumes and browser-smoke the chart through `http://127.0.0.1:8080`.
- Update `progress_tasks_newphases.md`, review the diff and secret exposure, commit, and push the phase branch. Do not force-push.

## Phase 2 — Verified live-index dashboard

**Outcome:** the landing market dashboard shows actual timestamped provider responses for supported indices, or a precise actionable blocker when live access is unavailable.

### Parallel tasks

1. **Credential readiness:** verify the stored Dhan token and client ID server-side without logging or returning them; distinguish missing, expired, unauthorized, and rate-limited states.
2. **Provider adapter:** implement bounded read-only quotes for NIFTY, BANKNIFTY, FINNIFTY, SENSEX, and India VIX where mappings and entitlements are independently verified.
3. **Freshness model:** persist/source event time, receipt time, provider, exchange session state, stale threshold, and failure reason; never replace failed quotes with zeroes.
4. **Dashboard UI:** add quote cards, connection status, last event/receipt time, stale/delayed badges, market-open state, retry behavior, and honest unavailable states.
5. **Observability/tests:** add mocked provider-contract tests, timeout/auth/rate-limit tests, cache tests, and browser coverage for live, stale, and unavailable states.

### Gate

At least one supported index shows a non-placeholder provider value with trustworthy timestamps, or the portal clearly identifies the exact credential/entitlement blocker. A health endpoint alone does not satisfy this gate.

### Final stage — build, commit, and push

- Integrate adapter, freshness contract, dashboard, monitoring, and tests.
- Run provider-contract tests without exposing tokens, frontend tests, production builds, and authenticated browser smoke tests.
- Record which symbols are verified and which remain unavailable.
- Update progress, review the diff and logs for secrets, commit, and push the phase branch. Do not force-push.

## Phase 3 — Option chain, OI, liquidity, and affordability

**Outcome:** the portal presents a verified, timestamped option chain suitable for research, without turning it into an order recommendation.

### Parallel tasks

1. **Chain ingestion:** implement bounded read-only expiry and option-chain retrieval with provider quotas, caching, provenance, and typed failure states.
2. **Contract normalization:** verify security ID, expiry, strike, CE/PE, lot size, tick size, LTP, bid/ask, volume, OI, change in OI, and provider units.
3. **Greeks policy:** display provider-supplied Greeks only when verified; otherwise show unavailable rather than locally inventing values.
4. **Option-chain UI:** add expiry selection, strike window, ATM reference, CE/PE columns, OI/volume/spread filters, freshness, and accessible table behavior.
5. **Affordability/risk:** calculate lot premium, spread cost, maximum premium loss, and capital requirement from verified contract metadata; label assumptions.
6. **Testing:** cover quotas, stale chains, partial rows, unit conversion, missing Greeks, and responsive table interaction.

### Gate

A verified NIFTY chain is visible with source/event/receipt time and exact-contract identity; missing fields and stale data are explicit; no buy/sell instruction is generated.

### Final stage — build, commit, and push

- Integrate chain ingestion, normalization, affordability, UI, and tests.
- Run backend/provider tests, frontend tests, accessibility/browser tests, and production builds.
- Smoke-test an authorized read-only chain request while respecting provider rate limits.
- Update progress, review secrets and data labels, commit, and push the phase branch. Do not force-push.

## Phase 4 — Breadth, sectors, momentum, and market structure

**Outcome:** the portal explains the current index context using synchronized, versioned evidence.

### Parallel tasks

1. **Universe and sectors:** verify NIFTY constituents, sector membership, weights, as-of date, and historical membership coverage.
2. **Breadth engine:** compute advancing/declining/unchanged counts, weighted participation, sector breadth, and coverage denominator from synchronized data.
3. **Structure engine:** expose prior range, VWAP, session high/low, swing zones, breakout/retest, and versioned order-block rules using completed bars only.
4. **Momentum scanner:** implement deterministic scanner rules with source freshness, eligibility, rejection reasons, and no-look-ahead tests.
5. **Portal views:** add breadth tiles, sector heatmap/table, structure levels, momentum watchlist, counter-evidence, and partial-universe warnings.
6. **Validation:** test data synchronization, incomplete universes, out-of-hours observations, rule versions, and UI interactions.

### Gate

Every displayed breadth or structure result includes its denominator, rule version, source times, missing-data state, and supporting/opposing evidence.

### Final stage — build, commit, and push

- Integrate engines, API contracts, portal views, and test suites.
- Run deterministic/no-look-ahead tests, frontend tests, browser/accessibility tests, and production builds.
- Smoke-test the real portal with partial-data behavior as well as the successful path.
- Update progress, review the diff, commit, and push the phase branch. Do not force-push.

## Phase 5 — Research validation and explainable watchlist

**Outcome:** historical candidates and rankings are clearly separated from live observations and supported by adequate samples.

### Parallel tasks

1. **Data expansion:** acquire verified multi-session CE/PE exact-contract histories across expiries and regimes without manufacturing missing sessions.
2. **Backtest validation:** enforce completed-bar decisions, next-available entry, costs, spread/slippage, liquidity assumptions, and adverse intrabar handling.
3. **Walk-forward/regime analysis:** run chronological out-of-sample checks and compare shortlisted versus rejected candidates and outages.
4. **Ranking evidence:** connect every score and rejection to source reports, sessions, rule versions, limitations, and null/undefined metrics.
5. **Research UI:** separate historical research from live watchlists; add provenance, sample-size warnings, counter-evidence, and accessible detail views.
6. **Testing:** cover reproducibility, sparse samples, undefined metrics, ranking API/UI contracts, and report fingerprints.

### Gate

No one-session result is presented as strategy readiness. Rankings are reproducible, visibly historical/simulated, and rejected when evidence thresholds are not met.

### Final stage — build, commit, and push

- Integrate data/report/ranking contracts and the research UI.
- Run backtest, walk-forward, ranking, frontend, browser, and production-build checks.
- Verify report fingerprints and provenance against persisted records.
- Update progress, review the diff, commit, and push the phase branch. Do not force-push.

## Phase 6 — Paper observation and server-side risk

**Outcome:** paper-only lifecycle and risk controls can consume verified data without creating a broker order.

### Parallel tasks

1. **Paper ledger:** verify account, intent, order, fill, position, and risk-event separation from broker state.
2. **Risk engine:** enforce exact lot/tick, quantity/value, capital, max loss, exposure, daily loss, session, eligibility, and stale-data blocks.
3. **Lifecycle/reconciliation:** test idempotency, partial/rejected fills, uncertain states, restart reconciliation, and candidate attribution.
4. **Kill switch:** verify persistent default-safe behavior, UI state, confirmation, concurrency, and recovery drills.
5. **Paper UI:** clearly label simulations, show data provenance, prevent ambiguous live-like wording, and disable controls when data is stale or unverified.
6. **Testing/operations:** execute bounded paper drills only; no Dhan, Angel One, or MT5 broker order endpoint may be called.

### Gate

All paper intents are auditable and blocked by stale/unverified data or the kill switch. Passing this phase does not authorize a broker demo order.

### Final stage — build, commit, and push

- Integrate paper services, risk controls, UI, and drills.
- Run paper/risk/concurrency/restart tests, frontend/browser tests, and production builds.
- Confirm network logs contain no broker order submission.
- Update progress, review the diff, commit, and push the phase branch. Do not force-push.

## Phase 7 — Operations, resilience, and release readiness

**Outcome:** the portal is maintainable, observable, recoverable, and honest during provider or infrastructure failures.

### Parallel tasks

1. **Backup/restore:** automate and verify PostgreSQL, historical partitions, credential-key, and configuration recovery with retention and off-host guidance.
2. **Monitoring:** add feed freshness, worker lag, provider errors, quotas, partition integrity, backup age, and frontend/API health without exposing secrets.
3. **Security:** verify authentication modes, same-origin behavior, secret handling, dependency/image scans, and localhost-only development overrides.
4. **Browser/accessibility:** test navigation, keyboard use, tables/charts, mobile behavior, error states, and supported browsers.
5. **Runbooks:** document startup with recovered volumes, provider credential rotation, stale-feed response, restore, rollback, and incident escalation.
6. **Release evidence:** produce a truthful feature/limitation matrix for live, delayed, historical, simulated, and unavailable capabilities.

### Gate

A fresh operator can restore and launch the stack, identify data freshness and failures, and roll back a release without deleting preserved data or enabling execution.

### Final stage — build, commit, and push

- Integrate operational changes and release documentation.
- Run the complete backend/frontend/E2E suite, Compose validation, image builds, restore drill, and browser smoke test.
- Confirm no secrets, generated cookies, local dumps, or credentials are staged.
- Update `progress_tasks_newphases.md` with final evidence and remaining limitations.
- Commit the release milestone and push the phase branch/tag according to the repository release policy. Never force-push or overwrite an immutable release tag.

## Separate future gates — not authorized by this roadmap

Broker demo execution and controlled live execution require separate plans and explicit approval for a named verified account, instrument, side, quantity, maximum risk, and time window. They are deliberately excluded from the parallel implementation phases above.