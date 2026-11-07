# Phase 4 — deterministic strategies and signals

Phase 4 adds a pure, broker-independent strategy boundary. `Candle`, `Source`, configuration and decision objects are frozen and versioned. Prices and indicator values use `Decimal`; timestamps must be timezone-aware UTC. Inputs identify the canonical instrument, provider mapping, historical import source checksum, immutable partition and partition checksum.

The explicit built-in registry contains one reference strategy, `option-premium-ema-rsi` version 1. It evaluates a bounded 1m/5m option-premium window and emits only `LONG` or `NONE`; this is a research signal, never an order. Configuration bounds and required history are validated. Gaps, duplicate intervals, missing volume, session/expiry mismatches and insufficient history produce rejection rather than fabricated data. EMA, RSI, ATR and VWAP define warm-up behavior; VWAP is undefined without volume or with zero total volume.

An operator can evaluate a previously imported fixture with:

```text
python -m app.cli evaluate-strategy --file <fixture.csv> --job-id <uuid> \
  --fast-period 3 --slow-period 5 --rsi-period 3 --rsi-floor 40 --rsi-ceiling 100
```

The command revalidates the exact fixture checksum, catalog metadata and on-disk partition checksum. Supply the same configured historical data root used for import. Accepted LONG outputs persist an immutable configuration version and exact JSON input/output snapshot through migration `0004`. Replaying identical input is idempotent. `NONE` and rejected evaluations are returned but are not represented as signals.

There is no dynamic strategy/plugin loading, provider call, broker call, order interface, execution capability, or Phase 5 backtest/catalog reader. Built-in code may later run in a separate process for operational fault isolation; process isolation alone is **not a security sandbox** and untrusted Python must not be loaded.
