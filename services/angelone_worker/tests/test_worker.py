import json

import pytest

from worker import ReadOnlyAngelOne, write_snapshot


class FakeResponse:
    status_code = 200

    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


class FakeHttp:
    def __init__(self):
        self.calls = []

    def post(self, path, **kwargs):
        self.calls.append((path, kwargs))
        if "loginByPassword" in path:
            return FakeResponse({"status": True, "data": {"jwtToken": "secret-token"}})
        return FakeResponse({"status": True, "data": {"ltp": "100.25"}})

    def close(self):
        pass


def test_worker_allowlists_login_and_ltp(tmp_path):
    connector = ReadOnlyAngelOne("api-key", "client", "pin", "seed")
    fake = FakeHttp()
    connector.client.close()
    connector.client = fake
    connector.authenticate()
    quote = connector.ltp("NSE", "NIFTY", "123")
    assert quote["ltp"] == "100.25"
    assert quote["event_time"] is None
    assert len(fake.calls) == 2
    output = tmp_path / "snapshot.json"
    write_snapshot(
        output,
        connector,
        [{"exchange": "NSE", "trading_symbol": "NIFTY", "symbol_token": "123"}],
    )
    assert len(fake.calls) == 3  # The existing session is reused, not regenerated.
    assert {call[0] for call in fake.calls} == {
        "/rest/auth/angelbroking/user/v1/loginByPassword",
        "/rest/secure/angelbroking/order/v1/getLtpData",
    }
    text = output.read_text()
    for secret in ("secret-token", "api-key", "client", "pin", "seed", "123"):
        assert secret not in text
    data = json.loads(text)
    assert data["orders_available"] is False
    assert data["quotes"][0]["event_time"] is None


@pytest.mark.parametrize("envelope", [{"status": True}, {"success": True}])
def test_search_accepts_successful_envelopes(envelope):
    connector = ReadOnlyAngelOne("api-key", "client", "pin", "seed")
    fake = FakeHttp()
    connector.client.close()
    connector.client = fake
    connector.authenticate()
    fake.post = lambda path, **kwargs: FakeResponse(
        {
            **envelope,
            "data": [
                {"exchange": "NSE", "tradingsymbol": "NIFTY", "symboltoken": "123"}
            ],
        }
    )
    assert len(connector.search("NSE", "NIFTY")) == 1
    connector.close()


@pytest.mark.parametrize(
    "envelope",
    [{"status": False}, {"success": False}, {"status": True, "success": False}, {}],
)
def test_search_rejects_failed_or_ambiguous_envelopes(envelope):
    connector = ReadOnlyAngelOne("api-key", "client", "pin", "seed")
    fake = FakeHttp()
    connector.client.close()
    connector.client = fake
    connector.authenticate()
    fake.post = lambda path, **kwargs: FakeResponse({**envelope, "data": []})
    with pytest.raises(RuntimeError, match="instrument lookup unavailable"):
        connector.search("NSE", "NIFTY")
    connector.close()


@pytest.mark.parametrize("envelope", [{"status": True}, {"success": True}])
def test_ltp_accepts_successful_envelopes(envelope):
    connector = ReadOnlyAngelOne("api-key", "client", "pin", "seed")
    fake = FakeHttp()
    connector.client.close()
    connector.client = fake
    connector.authenticate()
    fake.post = lambda path, **kwargs: FakeResponse(
        {**envelope, "data": {"ltp": "100.25"}}
    )
    assert connector.ltp("NSE", "NIFTY", "123")["ltp"] == "100.25"
    connector.close()


def test_ltp_rejects_explicit_failure_despite_success_flag():
    connector = ReadOnlyAngelOne("api-key", "client", "pin", "seed")
    fake = FakeHttp()
    connector.client.close()
    connector.client = fake
    connector.authenticate()
    fake.post = lambda path, **kwargs: FakeResponse(
        {"status": True, "success": False, "data": {"ltp": "100.25"}}
    )
    with pytest.raises(RuntimeError, match="market data unavailable"):
        connector.ltp("NSE", "NIFTY", "123")
    connector.close()
