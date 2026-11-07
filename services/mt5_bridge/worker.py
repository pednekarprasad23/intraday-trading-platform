"""Publish private read-only snapshots; never accept commands from the API."""

import argparse
import json
import os
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
import time
import tempfile

from bridge import ReadOnlyBridge


def snapshot(bridge, symbols):
    result = {
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "status": bridge.status(),
        "account": None,
        "positions": None,
        "history": None,
        "quotes": [],
        "errors": [],
    }
    for name, method in (
        ("account", bridge.account),
        ("positions", bridge.positions),
        ("history", bridge.history),
    ):
        try:
            result[name] = method()
        except Exception:
            result["errors"].append(name + " unavailable")
    for symbol in symbols:
        try:
            tick = bridge.quote(symbol)
            if tick:
                result["quotes"].append(asdict(tick))
        except Exception:
            result["errors"].append("quote unavailable")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--terminal", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--symbol", action="append", default=[])
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    if not args.output.parent.is_dir():
        parser.error("Private output directory must already exist")
    if args.output.is_symlink():
        parser.error("Snapshot path must not be a symbolic link")
    import MetaTrader5 as mt5

    bridge = ReadOnlyBridge(mt5, args.terminal)
    try:
        while True:
            if not bridge.status()["connected"]:
                bridge.close()
                bridge.connect()
            data = snapshot(bridge, args.symbol[:20])
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    encoding="utf-8",
                    dir=args.output.parent,
                    prefix="mt5-",
                    suffix=".tmp",
                    delete=False,
                ) as output:
                    temporary = Path(output.name)
                    json.dump(data, output, allow_nan=False)
                os.replace(temporary, args.output)
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
            print("Read-only snapshot updated; account data omitted from logs.")
            if args.once:
                break
            time.sleep(15)
    finally:
        bridge.close()


if __name__ == "__main__":
    main()
