"""Option-chain and OI ingestion from Dhan API.

Read-only, bounded ingestion of option-chain data including open interest,
volume, and bid/ask quotes. No broker order capability.

Usage:
    python -m app.market_data.oi_ingestion fetch --symbol NIFTY --expiry 2026-11-09
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import tempfile
import urllib.request
from datetime import datetime, date, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.database import SessionLocal
from app.historical.credentials import load_dhan_credentials, CredentialError
from app.config import get_settings


class OIResult:
    """Result of an option-chain fetch operation."""

    def __init__(
        self,
        security_id: int,
        expiry: str,
        oi_data: list[dict[str, Any]],
        source_sha256: str,
        retrieved_at: datetime,
    ):
        self.security_id = security_id
        self.expiry = expiry
        self.oi_data = oi_data
        self.source_sha256 = source_sha256
        self.retrieved_at = retrieved_at


def fetch_option_chain(
    security_id: int,
    exchange_segment: str,
    expiry: date,
    token: str,
    client_id: str = "",
) -> OIResult | None:
    """Fetch option chain from Dhan API.

    Args:
        security_id: NSE security ID (e.g., 13 for NIFTY)
        exchange_segment: "IDX_I" for index options
        expiry: expiry date
        token: Dhan access token
        client_id: Dhan client ID (optional, may be required for some endpoints)

    Returns:
        OIResult with open interest data, or None on error
    """
    url = "https://api.dhan.co/v2/optionchain"
    headers = {
        "access-token": token,
        "client-id": client_id,
        "Content-Type": "application/json",
    }

    body = {
        "UnderlyingScrip": security_id,
        "UnderlyingSeg": exchange_segment,
        "Expiry": expiry.isoformat(),
    }

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode(),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            payload = json.loads(response.read())

        if payload.get("status") != "success":
            return None

        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        source_sha256 = hashlib.sha256(raw.encode()).hexdigest()

        option_chain = payload.get("data", {}).get("oc", {})
        oi_data = []

        for strike_str, legs in option_chain.items():
            for option_type in ("ce", "pe"):
                leg = legs.get(option_type, {})
                if leg.get("oi", 0) > 0:  # Only include active contracts
                    oi_data.append({
                        "strike": Decimal(strike_str),
                        "option_type": option_type.upper(),
                        "oi": leg.get("oi", 0),
                        "volume": leg.get("volume", 0),
                        "last_price": Decimal(str(leg.get("last_price", 0))),
                        "bid_price": Decimal(str(leg.get("top_bid_price", 0))),
                        "bid_qty": leg.get("top_bid_quantity", 0),
                        "ask_price": Decimal(str(leg.get("top_ask_price", 0))),
                        "ask_qty": leg.get("top_ask_quantity", 0),
                        "implied_volatility": leg.get("implied_volatility"),
                    })

        return OIResult(
            security_id=security_id,
            expiry=expiry.isoformat(),
            oi_data=oi_data,
            source_sha256=source_sha256,
            retrieved_at=datetime.now(timezone.utc),
        )
    except Exception as e:
        print(f"Error fetching option chain: {e}")
        return None


def fetch_expiry_list(
    security_id: int,
    exchange_segment: str,
    token: str,
    client_id: str = "",
) -> list[date]:
    """Fetch available expiry dates for an index."""
    url = "https://api.dhan.co/v2/optionchain/expirylist"
    headers = {
        "access-token": token,
        "client-id": client_id,
        "Content-Type": "application/json",
    }

    body = {
        "UnderlyingScrip": security_id,
        "UnderlyingSeg": exchange_segment,
    }

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode(),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=20) as response:
            payload = json.loads(response.read())

        if payload.get("status") != "success":
            return []

        expiries = payload.get("data", [])
        return [date.fromisoformat(d) for d in expiries]
    except Exception:
        return []


def export_oi_csv(result: OIResult) -> bytes:
    """Export OI results to CSV format."""
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow([
        "strike", "option_type", "oi", "volume", "last_price",
        "bid_price", "bid_qty", "ask_price", "ask_qty", "iv",
    ])
    for row in result.oi_data:
        writer.writerow([
            row["strike"],
            row["option_type"],
            row["oi"],
            row["volume"],
            row["last_price"],
            row["bid_price"],
            row["bid_qty"],
            row["ask_price"],
            row["ask_qty"],
            row["implied_volatility"],
        ])
    return output.getvalue().encode("utf-8")


def main():
    """CLI entry point for OI ingestion."""
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["fetch", "list-expiries"])
    parser.add_argument("--symbol", default="NIFTY", help="Underlying symbol")
    parser.add_argument("--security-id", type=int, default=13, help="Dhan security ID")
    parser.add_argument("--exchange-segment", default="IDX_I", help="Exchange segment")
    parser.add_argument("--expiry", type=date.fromisoformat, help="Expiry date (YYYY-MM-DD)")
    args = parser.parse_args()

    try:
        with SessionLocal() as db:
            token, client_id = load_dhan_credentials(
                db, Path(get_settings().credential_key_path)
            )
    except (CredentialError, FileNotFoundError) as e:
        print(f"Credential error: {e}")
        return

    if args.command == "list-expiries":
        expiries = fetch_expiry_list(
            args.security_id, args.exchange_segment, token, client_id
        )
        for exp in expiries:
            print(exp.isoformat())
        return

    if args.command == "fetch":
        if args.expiry is None:
            print("Expiry date required for fetch")
            return

        result = fetch_option_chain(
            args.security_id, args.exchange_segment, args.expiry, token, client_id
        )
        if result is None:
            print("Failed to fetch option chain")
            return

        print(f"{result.expiry}: {len(result.oi_data)} active contracts")
        print(f"source_sha256: {result.source_sha256}")

        csv_data = export_oi_csv(result)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as f:
            f.write(csv_data)
            print(f"CSV written to: {f.name}")


if __name__ == "__main__":
    main()