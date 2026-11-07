# Phase 1 local development

## Scope and prerequisites

Docker with Linux containers and Compose is required. Node 22+ is optional for frontend development. Python runs in Docker; the current Windows host has no Python installation. This is a loopback-only development stack, not a production deployment. HTTP cookies omit Secure only in development; do not expose these ports publicly.

## Start (from repository root)

1. Copy `.env.example` to `.env` and set `POSTGRES_PASSWORD` to a unique URL-safe value. Do not commit this file. Database URL interpolation requires URL-safe characters.
2. Run `docker compose --env-file .env -p intraday -f deployment/compose/compose.yml up --build -d --wait`.
3. Run `docker compose --env-file .env -p intraday -f deployment/compose/compose.yml exec api python -m app.cli bootstrap` in your interactive terminal. Enter your email and a password of at least 14 characters. There is no default account or public registration.
4. Run `docker compose --env-file .env -p intraday -f deployment/compose/compose.yml exec api python -m app.cli seed-demo`.
5. Open `http://localhost:8080`. Sign in to view status and search the seven explicitly demo instruments.

Database and Redis have no published ports. API binds only to `127.0.0.1:8000`, web only to `127.0.0.1:8080`. Persistent named volumes survive ordinary `down` and restart. Never use `down -v` on data you wish to keep.

## Checks

```text
docker build -t intraday-api-phase1 apps/api
docker run --rm -v "<absolute-repository-path>/apps/api:/app" intraday-api-phase1 python -m pytest -q
docker run --rm -v "<absolute-repository-path>/apps/api:/app" intraday-api-phase1 ruff check app tests alembic
docker run --rm -v "<absolute-repository-path>/apps/api:/app" intraday-api-phase1 ruff format --check app tests alembic
npm --prefix apps/web ci
npm --prefix apps/web run build
npm --prefix apps/web test
npm --prefix apps/web audit
```

Backend direct dependencies are in `requirements.txt`, resolved Linux/Python 3.12 dependencies in `requirements.lock`. Regenerate the lock in the supported container after intentional updates and rerun tests/audit. Frontend uses `package-lock.json`. Do not install the Linux backend lock directly on Windows.

## Security boundaries and limitations

Sessions are random opaque tokens; only token hashes are Redis keys. Logout deletes the session and server-side TTL expires it after one hour. Redis failure fails authentication closed. Argon2id hashes passwords. Global single-user login throttling permits ten attempts per minute. SameSite Strict and origin checking protect browser mutations. Audit events contain no passwords or tokens. There are no order endpoints or broker dependencies.

Local HTTP is deliberately not HTTPS. Production TLS, MFA/recovery, backup/restore drills, external monitoring, static egress, and cloud deployment remain deferred. All fixtures are illustrative, including the option placeholder; they are not executable contracts or historical market data. Trading mode is a safety label, not a claim that a simulator exists.

## Phase 2 provider notes

Angel One is the selected provider direction, but Phase 2's current adapter boundary is offline-only until official access, entitlements, instrument-master source, and current WebSocket behavior are reviewed and explicitly configured. Never place TOTP seeds or SmartAPI tokens in this repository. The MT5 bridge is separate and Windows-only; see `services/mt5_bridge/README.md`.
