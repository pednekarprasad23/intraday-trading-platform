from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from bridge import ReadOnlyBridge, TerminalUnavailable
from worker import snapshot


class FakeTerminal:
    def __init__(self):
        self.shutdown_called = False
        self.connected = True
        self.positions_value = []
        self.history_value = []
        self.account_value = SimpleNamespace(
            currency="USD",
            balance=100,
            equity=101,
            profit=1,
            margin=5,
            margin_free=96,
            login=123456,
            name="private",
        )

    def initialize(self, **kwargs):
        self.kwargs = kwargs
        return True

    def shutdown(self):
        self.shutdown_called = True

    def terminal_info(self):
        return SimpleNamespace(connected=self.connected)

    def account_info(self):
        return self.account_value

    def positions_get(self):
        return self.positions_value

    def history_deals_get(self, start, end):
        assert (end - start).days == 7
        return self.history_value

    def symbol_info(self, symbol):
        return SimpleNamespace(name=symbol) if symbol == "TEST" else None

    def symbol_info_tick(self, symbol):
        return SimpleNamespace(time_msc=1730000000123, bid=12.25, ask=12.50)


def test_read_only_bridge():
    terminal = FakeTerminal()
    bridge = ReadOnlyBridge(terminal)
    assert bridge.status()["connected"] is False
    assert bridge.connect()
    assert terminal.kwargs == {"timeout": 5000}
    quote = bridge.quote("TEST")
    assert quote.bid == "12.25"
    assert (
        quote.event_time
        == datetime.fromtimestamp(1730000000.123, timezone.utc).isoformat()
    )
    assert bridge.quote("UNKNOWN") is None
    with pytest.raises(ValueError):
        bridge.quote("x" * 65)
    assert not hasattr(bridge, "order_send")
    assert "login" not in bridge.account()
    assert "123456" not in str(snapshot(bridge, ["TEST"]))
    assert bridge.positions() == []
    assert bridge.history() == []
    bridge.close()
    assert terminal.shutdown_called


def test_disconnected_and_unavailable_are_not_empty():
    terminal = FakeTerminal()
    bridge = ReadOnlyBridge(terminal)
    bridge.connect()
    terminal.connected = False
    with pytest.raises(TerminalUnavailable):
        bridge.positions()
    terminal.connected = True
    terminal.positions_value = None
    terminal.history_value = None
    terminal.account_value = None
    data = snapshot(bridge, [])
    assert (
        data["positions"] is None
        and data["history"] is None
        and data["account"] is None
    )
    assert set(data["errors"]) == {
        "positions unavailable",
        "history unavailable",
        "account unavailable",
    }
    with pytest.raises(ValueError):
        bridge.history(31)
