# Provider verification — Phase 2

Updated: 2026-11-07

## Angel One

The selected provider direction is Angel One SmartAPI. The reviewed official sources are:

- SmartAPI Python repository: https://github.com/angel-one/smartapi-python
- Official WebSocket V2 source: https://github.com/angel-one/smartapi-python/blob/main/SmartApi/smartWebSocketV2.py
- Official SmartConnect source: https://github.com/angel-one/smartapi-python/blob/main/SmartApi/smartConnect.py

Those sources show read-only `ltpData`, `getMarketData`, `getCandleData`, `searchScrip`, and `SmartWebSocketV2` subscription APIs. The WebSocket source documents LTP/QUOTE/SNAP_QUOTE/DEPTH modes and token-list subscriptions. It also exposes order methods in the SDK; this project intentionally does not import or expose those methods. Price scaling/units and an authoritative instrument-master download source are not sufficiently documented by the reviewed source; the offline adapter rejects payloads without an explicit verified `price_unit` and does not connect a real account.

Required before a real adapter connection: confirm current official authentication/session/TOTP handling, instrument-master endpoint/source and licensing, token timestamp/price semantics, entitlements, rate/subscription limits, reconnect behavior, and current broker access terms. No credentials were used in Phase 2.

## MT5

Official sources:

- Python integration documentation: https://www.mql5.com/en/docs/integration/python_metatrader5
- Package: https://pypi.org/project/MetaTrader5/
- Python 3.13 Windows installer: https://www.python.org/downloads/windows/

Verified locally: official CPython 3.13.17 64-bit is installed at the user-scoped Python location, and `MetaTrader5==5.0.6231` provides/imports a `cp313-cp313-win_amd64` wheel. The desktop MT5 terminal was not found in common installation locations and no terminal/account login was attempted. Real bridge connectivity is therefore pending user-controlled installation and explicit approval. The implemented bridge is offline/unit-tested and read-only; it has no order operations or network listener.
