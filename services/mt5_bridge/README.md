# Windows MT5 read-only bridge

Windows CPython 3.13.17 and MetaTrader5 5.0.6231 are installed in the isolated `.venv`. On 2026-11-07 the already-running terminal at `C:\Program Files\MetaTrader 5\terminal64.exe` passed a redacted initialization, connectivity, account availability and positions-read check. No order operations were called.

## Transport

The Windows worker publishes an atomic JSON snapshot every 15 seconds. It accepts no network requests or commands from the API. The optional Compose override mounts a dedicated snapshot directory **read-only** into the API. The authenticated `/api/v1/mt5/snapshot` route validates a bounded file and withholds expired (45 seconds), disconnected, malformed or missing snapshots. Quote event age is checked separately. The default Compose stack does not enable this integration.

Snapshots contain sensitive financial data even though account identifiers are omitted. Use a dedicated local directory with Windows ACL access limited to the running user, SYSTEM, and the Docker runtime as needed. Do not use a shared, synchronized, public or repository-tracked directory. Do not expose Docker or application ports publicly. Directory ACL enforcement and actual host-to-container mount behavior still need deployment verification.

## Optional activation (not yet verified end-to-end)

Create and restrict the private directory first. Supply its absolute path as `MT5_SNAPSHOT_DIR` in the shell running Compose. Start the worker in an interactive terminal:

```powershell
& "services\mt5_bridge\.venv\Scripts\python.exe" services\mt5_bridge\worker.py --terminal "C:\Program Files\MetaTrader 5\terminal64.exe" --output "<private-directory>\snapshot.json"
```

Add `--symbol` for each exact broker symbol (maximum 20), or `--once` for a single snapshot. No symbol selection or trading commands are performed. History is limited to seven days and 1,000 deals; larger results are reported unavailable, not truncated. Historical deals may include balance operations and are not a performance report.

```powershell
docker compose --env-file .env -p intraday -f deployment/compose/compose.yml -f deployment/compose/compose.mt5.yml up --build -d --wait
```

Sign in to view the MT5 section. Stop the worker with Ctrl+C; the UI expires its data. Do not run multiple workers against the same output file. The worker is not installed as an automatic service.

## Tests

```powershell
& "services\mt5_bridge\.venv\Scripts\python.exe" -m pytest -q -c services\mt5_bridge\pytest.ini services\mt5_bridge\tests
```

No order methods, generic RPC, login endpoints, broker credentials, or Linux MT5 imports are permitted. Angel One remains offline and separate.
