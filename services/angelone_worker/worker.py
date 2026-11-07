"""Outbound-only Angel One read-only connector.

Credentials are read from the process environment and never printed. This
worker exposes no HTTP listener and only calls the documented login and LTP
market-data endpoints; it never imports or invokes order methods.
"""

import argparse
import json
import os
import socket
import tempfile
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

import httpx
import pyotp


def successful_response(payload: object) -> bool:
    """Accept supported success flags without overriding an explicit failure."""
    return (
        isinstance(payload, dict)
        and payload.get("status") is not False
        and payload.get("success") is not False
        and (payload.get("status") is True or payload.get("success") is True)
    )


REQUEST_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "X-UserType": "USER",
    "X-SourceID": "WEB",
}


class ReadOnlyAngelOne:
    def __init__(self, api_key: str, client_code: str, pin: str, totp_seed: str):
        self.client_code = client_code
        self.pin = pin
        self.totp_seed = totp_seed
        self.client = httpx.Client(
            base_url="https://apiconnect.angelone.in",
            timeout=5.0,
            follow_redirects=False,
        )
        self.api_key = api_key
        mac = f"{uuid.getnode():012x}"
        self.device_headers = {
            "X-ClientLocalIP": socket.gethostbyname(socket.gethostname()),
            "X-ClientPublicIP": os.environ.get("ANGELONE_PUBLIC_IP", ""),
            "X-MACAddress": ":".join(mac[i : i + 2] for i in range(0, 12, 2)),
        }
        self.jwt_token: str | None = None
        self.authenticated = False

    def authenticate(self):
        self.authenticated = False
        self.jwt_token = None
        response = self.client.post(
            "/rest/auth/angelbroking/user/v1/loginByPassword",
            headers={
                **REQUEST_HEADERS,
                **self.device_headers,
                "X-PrivateKey": self.api_key,
            },
            json={
                "clientcode": self.client_code,
                "password": self.pin,
                "totp": pyotp.TOTP(self.totp_seed).now(),
            },
        )
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data") if isinstance(payload, dict) else None
        token = data.get("jwtToken") if isinstance(data, dict) else None
        if (
            not isinstance(payload, dict)
            or payload.get("status") is not True
            or not token
        ):
            raise RuntimeError("Angel One authentication failed")
        self.jwt_token = str(token)
        self.authenticated = True

    def search(self, exchange: str, query: str) -> list[dict]:
        if not self.authenticated or not self.jwt_token:
            raise RuntimeError("Angel One is not authenticated")
        if exchange != "NSE" or query not in {"NIFTY", "BANKNIFTY"}:
            raise ValueError("Only the approved NSE index searches are allowed")
        response = self.client.post(
            "/rest/secure/angelbroking/order/v1/searchScrip",
            headers={
                **REQUEST_HEADERS,
                **self.device_headers,
                "X-PrivateKey": self.api_key,
                "Authorization": f"Bearer {self.jwt_token}",
            },
            json={"exchange": exchange, "searchscrip": query},
        )
        response.raise_for_status()
        payload = response.json()
        if not successful_response(payload):
            raise RuntimeError("Angel One instrument lookup unavailable")
        rows = payload.get("data")
        if not isinstance(rows, list):
            raise RuntimeError("Angel One instrument lookup incomplete")
        return [row for row in rows if isinstance(row, dict)]

    def ltp(self, exchange: str, trading_symbol: str, symbol_token: str):
        if (
            exchange != "NSE"
            or trading_symbol not in {"NIFTY", "BANKNIFTY"}
            or not symbol_token.isdigit()
        ):
            raise ValueError("Only verified NSE index tokens are allowed")
        if not self.authenticated or not self.jwt_token:
            raise RuntimeError("Angel One is not authenticated")
        response = self.client.post(
            "/rest/secure/angelbroking/order/v1/getLtpData",
            headers={
                **REQUEST_HEADERS,
                **self.device_headers,
                "X-PrivateKey": self.api_key,
                "Authorization": f"Bearer {self.jwt_token}",
            },
            json={
                "exchange": exchange,
                "tradingsymbol": trading_symbol,
                "symboltoken": symbol_token,
            },
        )
        if response.status_code in (401, 403):
            self.authenticated = False
            self.jwt_token = None
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data") if isinstance(payload, dict) else None
        if (
            not isinstance(payload, dict)
            or not successful_response(payload)
            or not isinstance(data, dict)
        ):
            if (
                isinstance(payload, dict)
                and payload.get("error_type") == "TokenException"
            ):
                self.authenticated = False
                self.jwt_token = None
            raise RuntimeError("Angel One market data unavailable")
        try:
            price = Decimal(str(data.get("ltp")))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValueError("Angel One LTP is invalid") from exc
        if not price.is_finite() or price <= 0:
            raise ValueError("Angel One LTP is invalid")
        event_time = data.get("exchange_timestamp")
        if isinstance(event_time, str) and event_time:
            try:
                parsed = datetime.fromisoformat(event_time.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    event_time = None
            except ValueError:
                event_time = None
        else:
            event_time = None
        return {
            "symbol": trading_symbol,
            "ltp": str(price),
            "event_time": event_time,
            "received_at": datetime.now(timezone.utc).isoformat(),
            "provenance": "ANGEL_ONE",
        }

    def close(self):
        self.jwt_token = None
        self.authenticated = False
        self.client.close()


def write_snapshot(output: Path, connector: ReadOnlyAngelOne, instruments: list[dict]):
    result = {
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "provider": "ANGEL_ONE",
        "authenticated": False,
        "quotes": [],
        "errors": [],
        "orders_available": False,
    }
    if not connector.authenticated:
        try:
            connector.authenticate()
        except Exception:
            result["errors"].append("authentication unavailable")
    if connector.authenticated:
        for item in instruments[:20]:
            try:
                result["quotes"].append(
                    connector.ltp(
                        item["exchange"], item["trading_symbol"], item["symbol_token"]
                    )
                )
            except Exception:
                result["errors"].append("quote unavailable")
    result["authenticated"] = connector.authenticated
    if not connector.authenticated:
        result["quotes"].clear()
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output.parent,
            prefix="angelone-",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            json.dump(result, stream, allow_nan=False)
        os.replace(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--instrument", action="append", default=[], help="EXCHANGE:SYMBOL:TOKEN"
    )
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    if not args.output.parent.is_dir() or args.output.is_symlink():
        parser.error("Output directory must exist and output must not be a symlink")
    if not 1 <= len(args.instrument) <= 2:
        parser.error("Provide one or two verified NSE index instruments")
    instruments = []
    for raw in args.instrument:
        parts = raw.split(":", 2)
        if (
            len(parts) != 3
            or parts[0] != "NSE"
            or parts[1] not in {"NIFTY", "BANKNIFTY"}
            or not parts[2].isdigit()
        ):
            parser.error(
                "Only verified NSE:NIFTY:TOKEN or NSE:BANKNIFTY:TOKEN are allowed"
            )
        instruments.append(
            {"exchange": parts[0], "trading_symbol": parts[1], "symbol_token": parts[2]}
        )
    required = (
        "ANGELONE_API_KEY",
        "ANGELONE_CLIENT_CODE",
        "ANGELONE_PIN",
        "ANGELONE_TOTP_SEED",
    )
    if any(not os.environ.get(name) for name in required):
        parser.error(
            "Angel One credentials must be supplied through the private process environment"
        )
    connector = ReadOnlyAngelOne(*(os.environ[name] for name in required))
    try:
        connector.authenticate()
        for item in instruments:
            matches = [
                row
                for row in connector.search(item["exchange"], item["trading_symbol"])
                if row.get("exchange") == item["exchange"]
                and row.get("tradingsymbol") == item["trading_symbol"]
                and str(row.get("symboltoken")) == item["symbol_token"]
            ]
            if len(matches) != 1:
                parser.error(
                    "Instrument lookup did not uniquely verify the requested symbol/token"
                )
        while True:
            write_snapshot(args.output, connector, instruments)
            if args.once:
                return
            time.sleep(15)
    finally:
        connector.close()


if __name__ == "__main__":
    main()
