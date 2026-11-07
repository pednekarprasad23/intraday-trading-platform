from datetime import datetime, timezone
from types import SimpleNamespace

from bridge import ReadOnlyBridge


class FakeTerminal:
    def __init__(self):
        self.shutdown_called = False

    def initialize(self):
        return True

    def shutdown(self):
        self.shutdown_called = True

    def terminal_info(self):
        return SimpleNamespace(connected=True)

    def symbol_info(self, symbol):
        return SimpleNamespace(name=symbol) if symbol == "TEST" else None

    def symbol_info_tick(self, symbol):
        return SimpleNamespace(time_msc=1730000000123, bid=12.25, ask=12.50)


def test_read_only_bridge():
    terminal = FakeTerminal()
    bridge = ReadOnlyBridge(terminal)
    assert bridge.status() == {"connected": False, "orders_available": False, "python_runtime": "3.13-required"}
    assert bridge.connect()
    quote = bridge.quote("TEST")
    assert str(quote.bid) == "12.25"
    assert quote.event_time == datetime.fromtimestamp(1730000000.123, timezone.utc)
    assert bridge.quote("UNKNOWN") is None
    assert bridge.quote("x" * 65) is None
    assert not hasattr(bridge, "order_send")
    bridge.close()
    assert terminal.shutdown_called
