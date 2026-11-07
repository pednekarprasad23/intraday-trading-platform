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

A further read-only check on 2026-11-07 authenticated successfully and searched `NFO:NIFTY`. The broker returned option-like rows and one exact exchange/symbol/token match for a selected NIFTY call contract. A single `getLtpData` request for that exact match returned HTTP 200 with an unsuccessful broker response; no price was accepted or published. This establishes that option lookup can work but **does not** establish LTP entitlement, usable price semantics, or an operational option feed. No additional LTP attempts were made.

Still unresolved: instrument-master source and licensing, token and price semantics for selected instruments, account market-data entitlements (including the unsuccessful option LTP response), provider rate/subscription limits, and stable outbound static IP. Do not claim a live quote until a successful LTP call is observed.

## Constituent and sector coverage gate

No constituent, sector-membership, index-weight, or historical-reconstitution source is currently verified for this workspace. The existing Angel One and Dhan checks establish selected instrument lookup/historical access only; they do not provide an authorized index-universe snapshot or redistribution rights for constituent metadata. No constituent list, sector breadth, weight, or membership history is therefore published or used in research.

Before implementation, record for each index and as-of date: authoritative source and license/redistribution terms, constituent denominator, security identifiers and exchange, sector taxonomy/version, constituent weight basis and sum, effective date versus publication/retrieval time, corporate-action/reconstitution treatment, and missing/ambiguous mappings. The eventual provider-neutral contract must distinguish an index universe snapshot from a live quote feed and must preserve the source receipt/hash and coverage gaps. Until those checks pass, constituent breadth and sector calculations remain unavailable rather than inferred from the instrument catalog.

## Phase 3 historical provenance

The Phase 3 CSV fixtures are synthetic DEMO option bars, not licensed exchange/broker historical data. The import's `provider` + `provider_instrument_key` must resolve to exactly one preexisting option mapping; the SHA-256 identifies the exact input CSV bytes. Successful fixture import does not verify any real provider entitlement, activate `data_enabled`/`data_available`, or enable trading. Angel One historical entitlement, exact contract mapping and LTP are still unverified; no broker history endpoint is called.

## Dhan read-only historical research

Earlier private read-only checks on 2026-11-07 found an active Data API plan and one monthly NIFTY ATM rolling-option CE response containing 385 one-minute timestamps; that is rolling-series access only. Subsequently, a private token stored encrypted through the operator CLI supported a read-only exact-option verification. The official detailed instrument CSV identified a **unique** NSE/D/OPTIDX NIFTY 2026-11-09 26000 CE as security ID `40095` with underlying security ID `26000`; the verified mapping was recorded separately from DEMO instruments, with execution disabled. A bounded `/v2/charts/intraday` request for 2026-11-06 09:15–15:30 IST returned 375 contiguous one-minute bars, zero duplicates/gaps, and sanitized provider-response SHA-256 `af93d56e03496a7391e13ce91713bedf34632050b9b2ccab65c05f6c106819bb`. Dhan returned epoch seconds as integral floats and excluded the `fromDate` minute; the adapter now requests one minute earlier while validating the exact desired window. A 10-minute independent boundary probe confirmed the same semantics. The normalized fixture SHA-256 is `0a1aa94b54ae584d7655c39f8af1099ba4b8cc8b2a337cfa6010a1913d8d522e`. Raw response and credential were not retained in the research catalog. Exact-contract access and a bounded sample are now verified; broader price-unit/corporate-event reconciliation and contractual usage terms beyond documented local storage guidance are not independently established.

Official documentation: [intraday history](https://dhanhq.co/docs/v2/historical-data/) describes active security-ID instruments and parallel OHLCV/epoch-second timestamp arrays; [expired options](https://dhanhq.co/docs/v2/expired-options-data/) describes `rollingoption`, `drvOptionType`, `requiredData`, expiry code and ATM-relative strike with date-exclusive `toDate`. The implementation uses bounded operator-only calls and rejects relative series as exact contracts. Provider mapping and contract metadata must be verified separately before an exact import. Credentials stay out of the repository, browser and report API.

## MT5

Official sources:

- Python integration documentation: https://www.mql5.com/en/docs/integration/python_metatrader5
- Package: https://pypi.org/project/MetaTrader5/
- Python 3.13 Windows installer: https://www.python.org/downloads/windows/

Verified locally: official CPython 3.13.17 64-bit and `MetaTrader5==5.0.6231` cp313 wheel. The user subsequently installed/opened MT5 at `C:\Program Files\MetaTrader 5\terminal64.exe`; read-only initialize, connected status, account availability, positions request, and a redacted atomic snapshot succeeded. The optional API bind mount is read-only; the bridge has no order operations or network listener.
