# Provider verification — Phase 2

Updated: 2026-11-07

## Angel One

The selected provider direction is Angel One SmartAPI. The reviewed official sources are:

- SmartAPI Python repository: https://github.com/angel-one/smartapi-python
- Official WebSocket V2 source: https://github.com/angel-one/smartapi-python/blob/main/SmartApi/smartWebSocketV2.py
- Official SmartConnect source: https://github.com/angel-one/smartapi-python/blob/main/SmartApi/smartConnect.py

Those sources show read-only `ltpData`, `getMarketData`, `getCandleData`, `searchScrip`, and `SmartWebSocketV2` subscription APIs. The WebSocket source documents LTP/QUOTE/SNAP_QUOTE/DEPTH modes and token-list subscriptions. It also exposes order methods in the SDK; this project intentionally does not import or expose those methods. Price scaling/units and an authoritative instrument-master download source are not sufficiently documented by the reviewed source; the offline adapter rejects payloads without an explicit verified `price_unit` and does not connect a real account.

On 2026-11-07 the official `SmartConnect.generateSession(clientCode, password, totp)` source was rechecked: it POSTs `loginByPassword`, requires a current TOTP, and does not use a redirect callback. `ltpData(exchange, tradingsymbol, symboltoken)` POSTs `getLtpData` and passes the response through without establishing an exchange timestamp. A narrowly scoped local HTTP worker implements only those two documented paths and records receipt time; it does not fabricate an exchange event time. The user registered `https://tplatform.randomblog.site/angelone/callback`, but the callback is unused by this flow and must not forward to the local app.

A privately supplied credential set was used for a redacted, read-only server-side authentication check on 2026-11-07; authentication succeeded. An allowlisted NSE index instrument search returned HTTP 200 but a broker-level unsuccessful response (`success: false`), so no mapping was verified and no LTP call was made. The worker recognizes both `status` and `success` success envelopes but rejects explicit failures and contradictory flags. Tokens and credentials were not printed or committed.

Still unresolved: instrument-master source and licensing, token and price semantics for selected instruments, account market-data entitlements, provider rate/subscription limits, and stable outbound static IP. Do not claim a live quote until an allowlisted verified instrument and successful LTP call are observed.

## MT5

Official sources:

- Python integration documentation: https://www.mql5.com/en/docs/integration/python_metatrader5
- Package: https://pypi.org/project/MetaTrader5/
- Python 3.13 Windows installer: https://www.python.org/downloads/windows/

Verified locally: official CPython 3.13.17 64-bit and `MetaTrader5==5.0.6231` cp313 wheel. The user subsequently installed/opened MT5 at `C:\Program Files\MetaTrader 5\terminal64.exe`; read-only initialize, connected status, account availability, positions request, and a redacted atomic snapshot succeeded. The optional API bind mount is read-only; the bridge has no order operations or network listener.
