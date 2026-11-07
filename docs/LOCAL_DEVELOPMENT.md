# Phase 1 local development

## Scope and prerequisites

Docker with Linux containers and Compose is required. Node 22+ is optional for frontend development. The API uses Python in Docker. Windows CPython 3.13.17 is installed separately for the optional MT5 worker; see `services/mt5_bridge/README.md` for private snapshot setup. This is a loopback-only development stack, not a production deployment. HTTP cookies omit Secure only in development; do not expose these ports publicly.

## Start (from repository root)

1. Copy `.env.example` to `.env` and set `POSTGRES_PASSWORD` to a unique URL-safe value. Do not commit this file. Database URL interpolation requires URL-safe characters.
2. Run `docker compose --env-file .env -p intraday -f deployment/compose/compose.yml pull` then `docker compose --env-file .env -p intraday -f deployment/compose/compose.yml up -d --wait`. The default Compose file uses the published, versioned API and web images; PostgreSQL and Redis pull their official images. For explicit local source builds instead, add `-f deployment/compose/compose.build.yml` to the Compose command and use `up --build -d --wait`. The build override uses distinct `intraday-api:local` and `intraday-web:local` tags; do not mistake a local dashboard build for the currently published Docker Hub release.
3. Run `docker compose --env-file .env -p intraday -f deployment/compose/compose.yml exec api python -m app.cli bootstrap` in your interactive terminal. Enter your email and a password of at least 14 characters. There is no default account or public registration.
4. Run `docker compose --env-file .env -p intraday -f deployment/compose/compose.yml exec api python -m app.cli seed-demo`.
5. Open `http://localhost:8080`. Sign in to view status and search the seven explicitly demo instruments.

Database and Redis have no published ports. API binds only to `127.0.0.1:8000`, web only to `127.0.0.1:8080`. Persistent named volumes survive ordinary `down` and restart. Never use `down -v` on data you wish to keep. Preserve the same `.env` (especially `POSTGRES_PASSWORD`) across restarts: the database volume was initialized with that password. Preserve `intraday_postgres_data`, `intraday_redis_data`, `intraday_historical_data`, and `intraday_credential_key`. Removing images does not back up these volumes. The API and web images are currently public on Docker Hub and contain application code, not your local token or database records.

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

## Phase 3 offline historical fixture import

The API now has a persistent `historical_data` named volume at `/var/lib/intraday/historical`; back it up together with PostgreSQL. This is a research-only fixture import, not broker history. To use the synthetic 1m fixture, first run `seed-demo` (including on older stacks, to update illustrative option metadata). Copy `apps/api/tests/fixtures/DEMO_option_1m.csv` into the API container using your operator-controlled workflow (for example `docker cp` into an existing temporary directory; do not expose an upload endpoint). Compute SHA-256 of the exact CSV bytes using `sha256sum` or `Get-FileHash -Algorithm SHA256`, then run inside the API container:

```text
python -m app.cli import-candles --file /tmp/DEMO_option_1m.csv --provider DEMO --provider-key DEMO:OPTION --timeframe 1m --session-date 2026-11-06 --session-start 09:15 --session-end 09:18 --source-sha256 <lowercase-64-character-sha256>
```

For the independent 5m fixture use `DEMO_option_5m.csv`, timeframe `5m`, and window `09:15`–`09:25`. The demo option expires in 2030 and is deliberately **not** a tradeable instrument. Times and explicit windows are IST bar starts; timestamps in the CSV must include an offset. A declared fixture date is treated as a trading session for this import only. Other dates/holidays remain unknown; no calendar is inferred. Missing slots are reported, never generated. Repeating the same source and parameters returns the same job. A distinct source for an occupied partition is rejected for review, not merged.

Authenticated `GET /api/v1/historical/imports`, `/partitions`, and `/imports/{id}/gaps` return paginated catalog summaries (1–100 records) without filesystem paths. The CLI reports the completed job ID and row/duplicate/gap counts; failed validation exits without publishing a catalog entry. After a process crash or DB commit failure, run `python -m app.cli historical-orphans` to list unreferenced files; inspect these manually against the catalog before any retry or cleanup. The command does **not** delete anything. A file might be published before its catalog transaction commits; do not delete or overwrite it blindly. The CSV source itself is not retained by the importer; retain originals under your licensed data/backup policy. The root volume is not a substitute for off-host backup.

## Phase 2 provider notes

Angel One read-only server-side authentication and an exact NFO NIFTY option symbol/token match were verified on 2026-11-07, but the subsequent read-only LTP request returned an unsuccessful broker response. Market-data entitlement and a successful price response remain unverified. The registered redirect callback is not used by this server-side login flow; do not forward a public callback to the local app. See `services/angelone_worker/README.md` for the optional outbound-only worker. Never place TOTP seeds or SmartAPI tokens in the repository. The separate Windows-only MT5 bridge is described in `services/mt5_bridge/README.md`.
