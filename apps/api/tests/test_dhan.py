import json
from datetime import date, datetime, time, timezone
from decimal import Decimal
from hashlib import sha256

import pytest

from app.historical.dhan import ExactIdentity, fetch_exact, fetch_rolling
from app.historical.importer import _parse

DAY = date(2026, 11, 6)
START = time(9, 15)
END = time(9, 18)
TOKEN = "private-token-do-not-print"
EPOCH = int(datetime(2026, 11, 6, 3, 45, tzinfo=timezone.utc).timestamp())


def chart(stamps=None):
    stamps = stamps if stamps is not None else [EPOCH, EPOCH + 120]
    n = len(stamps)
    return {
        "timestamp": stamps,
        "open": [10] * n,
        "high": [11] * n,
        "low": [9] * n,
        "close": [10] * n,
        "volume": [0] * n,
    }


def identity(**changes):
    fields = dict(
        security_id="123",
        provider_key="123",
        expiry=date(2026, 12, 31),
        strike=Decimal("100"),
        option_type="CE",
        session_date=DAY,
        session_start=START,
        session_end=END,
        mapping_verified=True,
    )
    fields.update(changes)
    return ExactIdentity(**fields)


def exact(transport, **changes):
    return fetch_exact(
        identity=identity(**changes),
        exchange_segment="NSE_FNO",
        instrument="OPTIDX",
        timeframe="1m",
        token=TOKEN,
        transport=transport,
    )


def test_exact_fixture_gaps_duplicates_and_sanitized_provenance():
    calls = []

    def transport(url, body, headers, timeout):
        calls.append((url, json.loads(body), headers, timeout))
        return json.dumps(
            {
                **chart([EPOCH, EPOCH, EPOCH + 120]),
                "access_token": TOKEN,
                "other": {"authorization": TOKEN},
            }
        ).encode()

    result = exact(transport)
    assert len(result.bars) == 2
    assert result.bars[0].bar_time.isoformat() == "2026-11-06T03:45:00+00:00"
    assert result.gaps == (datetime.fromtimestamp(EPOCH + 60, timezone.utc),)
    assert result.duplicate_count == 1
    assert result.bars[0].volume == 0
    assert result.fixture_sha256 == sha256(result.fixture).hexdigest()
    rows, duplicates, gaps, _, _ = _parse(result.fixture, DAY, START, END, 1)
    assert len(rows) == 2 and duplicates == 0 and gaps == list(result.gaps)
    assert TOKEN not in repr(result) and TOKEN not in repr(result.provenance)
    assert (
        result.provenance.source_sha256
        == sha256(
            json.dumps(
                chart([EPOCH, EPOCH, EPOCH + 120]),
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
    )
    url, params, headers, timeout = calls[0]
    assert url == "https://api.dhan.co/v2/charts/intraday"
    assert params["interval"] == "1" and params["securityId"] == "123"
    assert params["fromDate"] == "2026-11-06 09:14:00"
    assert params["toDate"] == "2026-11-06 09:18:00"
    assert headers["access-token"] == TOKEN and TOKEN not in repr(params)
    assert timeout == 10


def test_integral_float_epoch_seconds_are_accepted():
    result = exact(
        lambda *args: json.dumps(chart([float(EPOCH), float(EPOCH + 120)])).encode()
    )
    assert result.bars[0].bar_time == datetime.fromtimestamp(EPOCH, timezone.utc)


def test_rolling_is_relative_and_never_exact():
    def transport(url, body, headers, timeout):
        assert url.endswith("/rollingoption")
        assert json.loads(body)["strike"] == "ATM+1"
        assert json.loads(body)["drvOptionType"] == "CALL"
        assert json.loads(body)["requiredData"] == [
            "open",
            "high",
            "low",
            "close",
            "volume",
        ]
        return json.dumps(
            {"data": {"ce": chart(), "pe": None}, "token": TOKEN}
        ).encode()

    result = fetch_rolling(
        security_id="13",
        exchange_segment="NSE_FNO",
        instrument="OPTIDX",
        expiry_flag="WEEK",
        expiry_code=0,
        strike="ATM+1",
        timeframe="1m",
        option_type="CALL",
        session_date=DAY,
        session_start=START,
        session_end=END,
        token=TOKEN,
        transport=transport,
    )
    assert len(result.ce) == 2 and len(result.pe) == 0
    assert len(result.ce_gaps) == 1 and len(result.pe_gaps) == 0
    assert not hasattr(result, "fixture") and not hasattr(result, "identity")
    assert TOKEN not in repr(result)


@pytest.mark.parametrize(
    "change",
    [
        {"mapping_verified": False},
        {"provider_key": "wrong"},
        {"option_type": "XX"},
        {"expiry": date(2026, 1, 1)},
        {"strike": Decimal("NaN")},
    ],
)
def test_exact_rejects_unverified_identity_before_network(change):
    with pytest.raises(ValueError):
        exact(lambda *args: pytest.fail("Unexpected network access"), **change)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda p: p.update(high=[]),
        lambda p: p.update(timestamp=[EPOCH * 1000, EPOCH + 120]),
        lambda p: p.update(timestamp=[EPOCH, EPOCH], high=[11, 12]),
        lambda p: p.update(timestamp=[EPOCH + 30, EPOCH + 120]),
        lambda p: p.update(timestamp=[EPOCH + 0.5, EPOCH + 120]),
        lambda p: p.update(open=[-1, 10]),
        lambda p: p.update(high=[8, 11]),
        lambda p: p.update(volume=[float("nan"), 0]),
        lambda p: p.update(timestamp=[]),
    ],
)
def test_invalid_arrays_fail_closed(mutate):
    payload = chart()
    mutate(payload)
    with pytest.raises(ValueError):
        exact(lambda *args: json.dumps(payload).encode())


def test_transport_errors_and_secret_never_escape():
    def failed(*args):
        raise RuntimeError(TOKEN)

    with pytest.raises(ValueError) as caught:
        exact(failed)
    assert TOKEN not in str(caught.value)
    assert caught.value.__cause__ is None and caught.value.__context__ is None
    with pytest.raises(ValueError) as caught:
        exact(lambda *args: b"{" + TOKEN.encode())
    assert TOKEN not in str(caught.value)
    with pytest.raises(ValueError):
        exact(lambda *args: b"x" * 5_000_001)


def test_rolling_rejects_missing_leg_and_invalid_selection():
    kwargs = dict(
        security_id="13",
        exchange_segment="NSE_FNO",
        instrument="OPTIDX",
        expiry_flag="WEEK",
        expiry_code=0,
        strike="ATM",
        timeframe="5m",
        option_type="CALL",
        session_date=DAY,
        session_start=time(9, 15),
        session_end=time(9, 25),
        token=TOKEN,
    )
    with pytest.raises(ValueError):
        fetch_rolling(**kwargs, transport=lambda *args: b'{"data":{"ce":{}}}')
    with pytest.raises(ValueError):
        fetch_rolling(
            **{**kwargs, "strike": "100CE"},
            transport=lambda *args: pytest.fail("Unexpected network access"),
        )
