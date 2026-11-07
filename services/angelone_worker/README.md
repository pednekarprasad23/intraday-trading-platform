# Angel One read-only worker

This worker is an outbound-only, server-side SmartAPI connector. It has no HTTP listener, browser callback, generic RPC, order method, or order-capable SDK call. It reads credentials only from the process environment, generates a current TOTP locally, requests LTP data for an explicit bounded instrument list, and writes an atomic local snapshot.

The official SmartAPI Python flow verified on 2026-11-07 uses `generateSession(client_code, PIN, current_TOTP)` and `ltpData(exchange, tradingsymbol, symboltoken)`. The worker calls only their corresponding documented REST paths through an isolated HTTP client. It does not require the registered redirect URL for this server-side flow. Therefore `https://tplatform.randomblog.site/angelone/callback` is not used by this worker. Do not forward it to the dashboard or API.

## Local isolated Python 3.13 environment

```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe" -m venv services\angelone_worker\.venv
& services\angelone_worker\.venv\Scripts\python.exe -m pip install -r services\angelone_worker\requirements.lock
& services\angelone_worker\.venv\Scripts\python.exe -m pytest -q -c services\angelone_worker\pytest.ini services\angelone_worker\tests
```

## Private environment

Supply these values through protected process/service configuration, never command-line arguments, chat, source control, browser code, or logs:

- `ANGELONE_API_KEY`
- `ANGELONE_CLIENT_CODE`
- `ANGELONE_PIN`
- `ANGELONE_TOTP_SEED`
- `ANGELONE_PUBLIC_IP` (non-secret actual registered outbound public IP, if required)

The current implementation generates a current OTP in memory and uses a JWT in memory, but does not persist any OTP, JWT, refresh token, or feed token in the snapshot. The API receives only normalized quote data. Use a dedicated private output directory with restrictive Windows ACLs.

## Instrument and run

Do not invent tokens or price semantics. For this first checkpoint, only NSE `NIFTY` and `BANKNIFTY` index lookups are allowed. The worker verifies each exact symbol/token with `searchScrip` before any LTP request and rejects ambiguous/unmatched results. An allowlisted NSE index search returned a broker-level unsuccessful response on 2026-11-07, so no token was verified and the worker has not fetched a real quote. Both successful `status` and `success` response envelopes are supported, but explicit failures are rejected. The LTP response has no verified exchange timestamp: the worker records receipt time, leaves event time null when absent, and marks quote event freshness unverified. Example shape:

```powershell
& services\angelone_worker\.venv\Scripts\python.exe services\angelone_worker\worker.py `
  --output C:\private\angelone\snapshot.json `
  --instrument NSE:NIFTY:EXCHANGE_VERIFIED_TOKEN `
  --once
```

Remove `--once` only under a supervised process. The worker polls every 15 seconds, reuses its session until an authentication failure, and retains no provider token in its output. Verify the actual outbound static IP before enabling; the registered callback domain is not the outbound API source IP. The optional API mount is:

```powershell
docker compose --env-file .env -p intraday `
  -f deployment/compose/compose.yml `
  -f deployment/compose/compose.angelone.yml up --build -d --wait
```

The authenticated API route is `/api/v1/angelone/snapshot`; it expires snapshots after 45 seconds and is disabled unless both `ANGELONE_ENABLED=true` and `ANGELONE_SNAPSHOT_PATH` are configured. No order operation is implemented or enabled.
