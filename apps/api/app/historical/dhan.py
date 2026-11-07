"""Read-only, bounded Dhan v2 historical charts; no catalog or DB writes.

Rolling option series are relative-to-ATM observations, never exact contracts.
The caller must independently verify all exact-contract identity and mapping fields.
"""

import csv
import hashlib
import io
import json
import re
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
BASE_URL = "https://api.dhan.co/v2/charts/"
MAX_RESPONSE_BYTES = 5_000_000
MAX_BARS = 50_000
TIMEOUT_SECONDS = 10
_SECRET_KEYS = {
    "access-token",
    "access_token",
    "token",
    "authorization",
    "api_key",
    "apikey",
    "client_id",
}
_COLUMNS = ("bar_time", "open", "high", "low", "close", "volume")


@dataclass(frozen=True)
class Bar:
    bar_time: datetime  # UTC
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal


@dataclass(frozen=True)
class Provenance:
    endpoint: str
    request: tuple[tuple[str, str], ...]  # public request parameters only
    source_sha256: str  # canonical JSON of sanitized provider response
    retrieved_at: datetime  # UTC receipt time, not an exchange event timestamp


@dataclass(frozen=True)
class ExactIdentity:
    """Externally verified identity; never constructed from rolling observations."""

    security_id: str
    provider_key: str
    expiry: date
    strike: Decimal
    option_type: str
    session_date: date
    session_start: time
    session_end: time
    mapping_verified: bool


@dataclass(frozen=True)
class ExactResult:
    identity: ExactIdentity
    timeframe: str
    bars: tuple[Bar, ...]
    gaps: tuple[datetime, ...]
    duplicate_count: int
    provenance: Provenance
    fixture: bytes  # validated CSV bytes; caller may persist and pass to import_fixture

    @property
    def fixture_sha256(self) -> str:
        return hashlib.sha256(self.fixture).hexdigest()


@dataclass(frozen=True)
class RollingResult:
    timeframe: str
    ce: tuple[Bar, ...]
    pe: tuple[Bar, ...]
    ce_gaps: tuple[datetime, ...]
    pe_gaps: tuple[datetime, ...]
    provenance: Provenance
    # Neither these observations nor the request establish an exact contract.


def _decimal(value, *, volume=False):
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        raise ValueError("Invalid OHLCV number")
    try:
        number = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("Invalid OHLCV number") from exc
    precision = 20 if volume else 18
    if (
        not number.is_finite()
        or number < (0 if volume else Decimal("0.0001"))
        or number.as_tuple().exponent < -4
        or number >= Decimal(10) ** (precision - 4)
        or len(number.as_tuple().digits) + max(number.as_tuple().exponent, 0)
        > precision
    ):
        raise ValueError("Invalid OHLCV number")
    return number


def _window(day, start, end, timeframe):
    if (
        not isinstance(day, date)
        or isinstance(day, datetime)
        or timeframe not in {"1m", "5m"}
    ):
        raise ValueError("Explicit date and 1m/5m timeframe required")
    if (
        not isinstance(start, time)
        or not isinstance(end, time)
        or start.tzinfo is not None
        or end.tzinfo is not None
        or start.second
        or start.microsecond
        or end.second
        or end.microsecond
    ):
        raise ValueError("Invalid IST session window")
    opened, closed = datetime.combine(day, start, IST), datetime.combine(day, end, IST)
    step = timedelta(minutes=int(timeframe[0]))
    if (
        closed <= opened
        or (closed - opened) % step
        or (closed - opened) // step > MAX_BARS
    ):
        raise ValueError("Invalid or oversized IST session window")
    return opened.astimezone(timezone.utc), closed.astimezone(timezone.utc), step


def _identifier(value, label):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", value):
        raise ValueError(f"Invalid {label}")
    return value


def _sanitize(value):
    if isinstance(value, dict):
        cleaned = {
            k: _sanitize(v)
            for k, v in value.items()
            if isinstance(k, str)
            and k.lower().replace("-", "_")
            not in {x.replace("-", "_") for x in _SECRET_KEYS}
        }
        return {k: v for k, v in cleaned.items() if v != {}}
    if isinstance(value, list):
        return [_sanitize(v) for v in value]
    return value


def _transport(url, body, headers, timeout):
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        if response.status != 200:
            raise ValueError("Dhan historical request failed")
        raw = response.read(MAX_RESPONSE_BYTES + 1)
    return raw


def _fetch(endpoint, params, token, transport):
    if (
        not isinstance(token, str)
        or not token
        or any(ord(c) < 33 or ord(c) > 126 for c in token)
    ):
        raise ValueError("Invalid access token")
    if endpoint not in {"intraday", "rollingoption"}:
        raise ValueError("Invalid endpoint")
    raw_request = json.dumps(params, separators=(",", ":"), allow_nan=False).encode(
        "utf-8"
    )
    try:
        raw = (transport or _transport)(
            BASE_URL + endpoint,
            raw_request,
            {"access-token": token, "Content-Type": "application/json"},
            TIMEOUT_SECONDS,
        )
        if not isinstance(raw, bytes) or len(raw) > MAX_RESPONSE_BYTES:
            raise ValueError("Invalid or oversized Dhan response")
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("Invalid Dhan response")
    except ValueError:
        error_message = "Invalid Dhan historical response"
    except Exception:
        # Provider exceptions may contain request headers; never chain or log them.
        error_message = "Dhan historical request failed"
    else:
        error_message = None
    if error_message is not None:
        raise ValueError(error_message)
    sanitized = _sanitize(payload)
    digest = hashlib.sha256(
        json.dumps(
            sanitized,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    public = tuple(sorted((key, str(value)) for key, value in params.items()))
    return payload, Provenance(endpoint, public, digest, datetime.now(timezone.utc))


def _bars(payload, opened, closed, step):
    if not isinstance(payload, dict):
        raise ValueError("Invalid chart arrays")
    keys = ("timestamp", "open", "high", "low", "close", "volume")
    arrays = [payload.get(k) for k in keys]
    if (
        any(not isinstance(a, list) for a in arrays)
        or not 0 < len(arrays[0]) <= MAX_BARS
        or any(len(a) != len(arrays[0]) for a in arrays)
    ):
        raise ValueError("Invalid chart arrays")
    found = {}
    duplicates = 0
    for values in zip(*arrays):
        stamp = values[0]
        if (
            isinstance(stamp, bool)
            or not isinstance(stamp, (int, float))
            or not float(stamp).is_integer()
        ):
            raise ValueError("Expected integral epoch-second timestamp")
        try:
            utc = datetime.fromtimestamp(int(stamp), timezone.utc)
        except (OverflowError, OSError, ValueError) as exc:
            raise ValueError("Invalid epoch-second timestamp") from exc
        if not opened <= utc < closed or (utc - opened) % step:
            raise ValueError("Bar outside or misaligned with IST session")
        nums = tuple(_decimal(v, volume=i == 4) for i, v in enumerate(values[1:]))
        opening, high, low, closing, _volume = nums
        if low > min(opening, closing) or high < max(opening, closing) or high < low:
            raise ValueError("Invalid OHLC")
        if utc in found:
            if found[utc] != nums:
                raise ValueError("Conflicting duplicate bar")
            duplicates += 1
        else:
            found[utc] = nums
    bars = tuple(Bar(stamp, *nums) for stamp, nums in sorted(found.items()))
    gaps = tuple(
        opened + i * step
        for i in range((closed - opened) // step)
        if opened + i * step not in found
    )
    return bars, gaps, duplicates


def _params(security_id, exchange_segment, instrument, timeframe, day, start, end):
    opened, closed, step = _window(day, start, end, timeframe)
    # The observed intraday chart excludes fromDate and includes bars before
    # toDate. Request one bar earlier, then validate against the desired window.
    requested_open = opened - step
    params = {
        "securityId": _identifier(security_id, "security ID"),
        "exchangeSegment": _identifier(exchange_segment, "exchange segment"),
        "instrument": _identifier(instrument, "instrument"),
        "interval": timeframe[:-1],
        "fromDate": requested_open.astimezone(IST).strftime("%Y-%m-%d %H:%M:%S"),
        "toDate": closed.astimezone(IST).strftime("%Y-%m-%d %H:%M:%S"),
    }
    return params, opened, closed, step


def fetch_exact(
    *,
    identity: ExactIdentity,
    exchange_segment: str,
    instrument: str,
    timeframe: str,
    token: str,
    transport=None,
) -> ExactResult:
    """Get active exact instrument candles; verified mapping remains caller's responsibility."""
    if not isinstance(identity, ExactIdentity) or not identity.mapping_verified:
        raise ValueError("Externally verified exact mapping required")
    _identifier(identity.provider_key, "provider mapping")
    if identity.provider_key != identity.security_id:
        raise ValueError("Provider mapping must match requested security ID")
    if (
        identity.option_type not in {"CE", "PE"}
        or not isinstance(identity.expiry, date)
        or isinstance(identity.expiry, datetime)
        or identity.expiry < identity.session_date
        or _decimal(identity.strike) <= 0
    ):
        raise ValueError("Invalid externally verified exact option identity")
    params, opened, closed, step = _params(
        identity.security_id,
        exchange_segment,
        instrument,
        timeframe,
        identity.session_date,
        identity.session_start,
        identity.session_end,
    )
    payload, provenance = _fetch("intraday", params, token, transport)
    bars, gaps, duplicates = _bars(payload, opened, closed, step)
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(_COLUMNS)
    for bar in bars:
        writer.writerow(
            (
                bar.bar_time.isoformat(),
                bar.open,
                bar.high,
                bar.low,
                bar.close,
                bar.volume,
            )
        )
    fixture = stream.getvalue().encode("utf-8")
    if len(fixture) > MAX_RESPONSE_BYTES:
        raise ValueError("Oversized CSV fixture")
    return ExactResult(identity, timeframe, bars, gaps, duplicates, provenance, fixture)


def fetch_rolling(
    *,
    security_id: str,
    exchange_segment: str,
    instrument: str,
    expiry_flag: str,
    expiry_code: int,
    strike: str,
    timeframe: str,
    option_type: str,
    session_date: date,
    session_start: time,
    session_end: time,
    token: str,
    transport=None,
) -> RollingResult:
    """Get relative-ATM CE/PE observations; cannot produce an exact-contract fixture."""
    params, opened, closed, step = _params(
        security_id,
        exchange_segment,
        instrument,
        timeframe,
        session_date,
        session_start,
        session_end,
    )
    if (
        expiry_flag not in {"WEEK", "MONTH"}
        or isinstance(expiry_code, bool)
        or not isinstance(expiry_code, int)
        or not 0 <= expiry_code <= 10
    ):
        raise ValueError("Invalid rolling expiry selection")
    if not isinstance(strike, str) or not re.fullmatch(
        r"ATM(?:[+-](?:[1-9]|1[0-9]|20))?", strike
    ):
        raise ValueError("Invalid relative ATM strike")
    if option_type not in {"CALL", "PUT"}:
        raise ValueError("Invalid rolling option type")
    params = {
        **params,
        "expiryFlag": expiry_flag,
        "expiryCode": expiry_code,
        "strike": strike,
        "drvOptionType": option_type,
        "requiredData": ["open", "high", "low", "close", "volume"],
        "fromDate": session_date.isoformat(),
        "toDate": (session_date + timedelta(days=1)).isoformat(),
    }
    payload, provenance = _fetch("rollingoption", params, token, transport)
    data = payload.get("data")
    branch = "ce" if option_type == "CALL" else "pe"
    if not isinstance(data, dict) or not isinstance(data.get(branch), dict):
        raise ValueError("Missing requested rolling option branch")
    bars, gaps, _ = _bars(data[branch], opened, closed, step)
    return RollingResult(
        timeframe,
        bars if branch == "ce" else (),
        bars if branch == "pe" else (),
        gaps if branch == "ce" else (),
        gaps if branch == "pe" else (),
        provenance,
    )
