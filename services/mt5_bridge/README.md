# Windows MT5 read-only bridge

This package is isolated from the Linux FastAPI container and is intended for the Windows host where the MetaTrader 5 desktop terminal is installed. It exposes no network listener and contains no order method. `ReadOnlyBridge` allows only terminal initialization/status and bounded symbol quotes through an injected terminal object.

## Host prerequisite verified

- Official Windows CPython **3.13.17 (64-bit)** installed with `winget` as `Python.Python.3.13`.
- `MetaTrader5==5.0.6231` has an official `cp313-cp313-win_amd64` wheel and imports successfully in `services/mt5_bridge/.venv`.
- The MT5 desktop terminal itself was not found in common installation directories and no live terminal/account connection was attempted. Real quote integration remains blocked until the user installs/opens the terminal and authorizes a read-only check.

## Local verification

```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe" -m venv services\mt5_bridge\.venv
& "services\mt5_bridge\.venv\Scripts\python.exe" -m pip install -r services\mt5_bridge\requirements.lock
& "services\mt5_bridge\.venv\Scripts\python.exe" -m pytest -q -c services\mt5_bridge\pytest.ini services\mt5_bridge\tests
```

Do not expose this bridge publicly, add a generic RPC endpoint, pass broker credentials through command arguments, or add order methods. A future authenticated loopback/outbound integration needs a separately approved network design, secret handling, terminal lifecycle policy, and reconciliation safety review. The `MetaTrader5` module communicates with a locally installed terminal; it is not suitable for import into the Linux API image.
