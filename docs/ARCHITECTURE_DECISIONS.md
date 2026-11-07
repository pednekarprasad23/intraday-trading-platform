# Architecture decisions — Phase 1

Approved 2026-11-07: retain the broad market/product vision, use React/TypeScript/Vite/Tailwind, start with local Docker Compose and a foundation/dashboard vertical slice. This supersedes Next.js and immediate cloud deployment requirements in the original blueprint for this phase. Preserve those documents as historical requirements, not contradictory implementation instructions.

FastAPI is a modular monolith. Current modules separate configuration, persistence models, authentication, local administrative commands and read-only API routes. Migrations live alongside the API at `apps/api/alembic` for reproducible container execution. PostgreSQL is durable storage; Redis provides expiring sessions/throttling. Web communicates only through same-origin `/api` proxy routes.

Future market-data, strategy, risk, execution and research modules will be separate application/domain boundaries. Do not add placeholder executable trading services now. Lightweight Charts is deferred until actual charting is approved; no fabricated prices are charted. No broker SDK, AI client or Parquet/DuckDB dependency is needed in Phase 1.

All money/contract decimal columns use NUMERIC/Decimal; PostgreSQL timestamps use TIMESTAMPTZ and UTC-aware application defaults. Canonical instruments and provider keys are separate. Fixtures use the DEMO namespace and eligibility is false. Audit events have no update/delete API.

Phase roadmap: 1 foundation; 2 verified provider market-data and instruments; 3 historical ingestion/quality; 4 strategies; 5 backtesting; 6 paper execution/risk; 7 TradingView paper-only webhooks; 8 live-execution planning only; 9 analytics/dashboard; 10 cloud and operational hardening. Each phase requires separate approval. The user selected Angel One as the intended broker-data provider; the DhanHQ reference in the original phase prompt is superseded. MT5 is a separate Windows-host read-only bridge under Python 3.13, with no order capability.
