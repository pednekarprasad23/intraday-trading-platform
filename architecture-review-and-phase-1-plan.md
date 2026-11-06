# Architecture Review and Phase 1 Plan

## Context

The repository is a documentation-only Git repository with no source code, dependency manifests, tests, migrations, containers, CI, or deployment files. The planning material contains one important conflict: `CLAUDE.md.txt` and the architecture document name Next.js and a broad multi-market product, while `also/CLAUDE.md` and `also/PHASE_PROMPTS.md` define React/Vite/Tailwind/Lightweight Charts and an initially NIFTY-focused options platform. The approved direction for this work is hybrid: preserve the broader product vision and safety requirements, but use the Vite frontend and implement NIFTY-first scope incrementally. Phase 1 is local Docker Compose only; cloud deployment is deferred. The first checkpoint includes the foundation plus a small dashboard vertical slice.

The system must remain paper/research-only during initial development. No broker integration, live market feed, live credentials, live orders, or autonomous trading will be implemented in Phase 1.

## Recommended architecture

Use a modular monolith with isolated worker boundaries that can be split later only when justified:

- `apps/web`: React + TypeScript + Vite + Tailwind + Lightweight Charts; UI and typed API client only.
- `apps/api`: FastAPI application with versioned routes, authentication, health/status, instrument queries, configuration, and application services.
- `packages/domain` / backend domain modules: broker-independent contracts and domain models for instruments, market data, strategies, risk, and execution. Phase 1 defines boundaries without implementing later trading capabilities.
- PostgreSQL: durable source of truth, accessed through SQLAlchemy and Alembic; UTC-aware timestamps and `Decimal` for financial values.
- Redis: local infrastructure dependency reserved for health/status and future queues/cache; never the durable source of truth.
- Docker Compose: local web, API, PostgreSQL, and Redis development environment.
- Configuration: environment variables with `.env.example`; no secrets in source control.

The browser will never contact broker APIs. Future order paths must pass through central risk checks, explicit approval, idempotency protection, and reconciliation. TimescaleDB, broker adapters, real data providers, AI integration, and cloud infrastructure remain out of Phase 1.

## Phase 1 implementation scope

1. Establish repository conventions and layout, including `.gitignore`, formatting, linting, type checking, dependency pinning, and beginner-friendly setup documentation.
2. Create local Docker Compose services for the web app, FastAPI API, PostgreSQL, and Redis, with health checks and safe development defaults.
3. Build FastAPI configuration, structured logging, correlation/request IDs, versioned health routes (`/api/v1/health/live`, `/api/v1/health/ready`), and `/api/v1/system/status`.
4. Add SQLAlchemy/Alembic foundation and the minimum Phase 1 durable model: single-user/authentication records as approved, audit records needed for security events, canonical instruments, and provider mappings. Use explicit demo fixtures only; do not present fabricated values as live prices.
5. Add a single-user authentication scaffold with Argon2id password hashing, secure HttpOnly session cookies, expiry, logout, rate limiting appropriate for local development, and no public registration. Keep paper/live separation explicit even though live mode is unavailable.
6. Build the Vite dashboard shell with login, service health/status cards, instrument list/search, loading/error/empty states, and prominent demo-data labeling. Add a typed API client and no broker or secret handling in the browser.
7. Add automated unit/integration/contract tests for configuration, UTC timestamp handling, health/readiness, migrations on an empty database, authentication/session behavior, instrument fixtures/API, and frontend API/status states.
8. Add CI checks for backend tests/lint/type checks, frontend lint/type checks/build, migration validation, dependency/security scanning where practical, and reproducible local commands.
9. Update project documentation with the selected hybrid direction, Phase 1 boundaries, local setup, acceptance criteria, and unresolved risks. Do not rewrite existing planning documents without reviewing their impact.

## Critical files and directories

- Existing requirements and constraints: `README.md`, `CLAUDE.md.txt`, `also/CLAUDE.md`, `also/PHASE_PROMPTS.md`.
- Product and architecture references: `docs/01-PRD.md`, `docs/02-SYSTEM-ARCHITECTURE.md`, `docs/03-DATABASE-DESIGN.md`, `docs/04-FIRST-DEVELOPMENT-SPRINT.md`.
- New implementation areas: `apps/web/`, `apps/api/`, `packages/` or backend domain modules, `database/migrations/`, `tests/`, `deployment/compose/`, and CI workflow files.
- Checkpoint tracking to add/update after implementation: `docs/PROJECT_STATUS.md` and `docs/CHANGELOG.md`.

## Dependencies to select and pin during implementation

Backend: Python, FastAPI, Pydantic Settings, SQLAlchemy, Alembic, PostgreSQL driver, Redis client, Argon2id library, structured logging, pytest, and type/lint tooling. Frontend: Node.js, React, TypeScript, Vite, Tailwind, Lightweight Charts, typed API tooling, and lint/type/build tooling. Infrastructure: Docker Compose, PostgreSQL, and Redis. Exact supported versions must be chosen from current stable compatible releases and captured in lockfiles/manifests; no broker SDK is required in Phase 1.

## Risks and unresolved requirements

- The broad PRD names Angel One and MT5, while the phased plan names DhanHQ; Phase 2 must verify the intended provider and current official documentation before any adapter work.
- Cloud vendor/region, static egress requirements, historical data provider/licensing, Qwen/Salad endpoint/model, retention, observability, and regulatory requirements remain undecided.
- Authentication is initially single-user; MFA, recovery, and future multi-user behavior need a later explicit design.
- Credible options backtesting requires real historical contract/premium data; no synthetic historical options data may be used as evidence.
- The local foundation must avoid accidentally exposing health endpoints, demo fixtures, or development credentials as production-ready behavior.

## Phase 1 acceptance criteria

- A clean checkout can start the local Compose stack without committed secrets.
- Live and readiness endpoints distinguish process health from dependency readiness.
- PostgreSQL migrations apply successfully to an empty database and are repeatable in CI.
- The user can authenticate, see session expiry/logout behavior, and access protected status/instrument views.
- The dashboard clearly labels demo instruments/data and never claims demo values are live market prices.
- Instrument/provider mappings are persisted and served through a versioned API.
- Frontend and backend automated checks pass, including tests for UTC-aware timestamps and security-sensitive authentication behavior.
- No broker API, live order path, autonomous trading path, or real credentials are present.
- `docs/PROJECT_STATUS.md` and `docs/CHANGELOG.md` record the checkpoint, test commands/results, remaining risks, and the exact approval gate for Phase 2.

## Verification and checkpoint

After implementation, run backend tests, frontend tests/type checks/build, linting, migration-up/down or clean-database validation, and a Compose smoke test covering health, login, status, and instrument listing. Review the complete Git diff for accidental secrets and unsafe live-trading paths. Summarize changed files, commands and outputs, known failures, pending decisions, and recommended next steps. Stop after Phase 1 and request approval before beginning Phase 2 market-data/provider work.
