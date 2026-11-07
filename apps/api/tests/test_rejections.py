"""Tests for the rejection rule engine."""

from decimal import Decimal

from app.research.rejections import VERSION, REJECTION_RULES, check_rejections


class TestVersion:
    def test_version_is_one(self):
        assert VERSION == 1


class TestWeightsSumToOne:
    def test_rulebook_weights_sum_to_one(self):
        from app.research.rulebook import SCORING_WEIGHTS
        total = sum(SCORING_WEIGHTS.values())
        assert total == Decimal("1.0")


class TestThresholds:
    def test_min_trades_rejects_below(self):
        is_rejected, reasons = check_rejections({"trade_count": 3}, 5)
        assert is_rejected
        assert any("INSUFFICIENT_TRADES" in r for r in reasons)

    def test_min_trades_accepts_above(self):
        is_rejected, reasons = check_rejections({"trade_count": 10}, 5)
        assert not is_rejected

    def test_min_trades_accepts_at_threshold(self):
        is_rejected, reasons = check_rejections({"trade_count": REJECTION_RULES["min_trades"]}, 5)
        assert not is_rejected

    def test_max_drawdown_rejects(self):
        metrics = {"max_drawdown": "60", "net_pnl": "100"}
        is_rejected, reasons = check_rejections(metrics, 5)
        assert is_rejected
        assert any("EXCESSIVE_DRAWDOWN" in r for r in reasons)

    def test_max_drawdown_accepts_within_pct(self):
        metrics = {"max_drawdown": "40", "net_pnl": "100", "trade_count": 10}
        is_rejected, reasons = check_rejections(metrics, 5)
        assert not is_rejected

    def test_min_win_rate_rejects(self):
        is_rejected, reasons = check_rejections({"win_rate": "0.2", "trade_count": 10}, 5)
        assert is_rejected
        assert any("LOW_WIN_RATE" in r for r in reasons)

    def test_min_win_rate_accepts(self):
        is_rejected, reasons = check_rejections({"win_rate": "0.4", "trade_count": 10}, 5)
        assert not is_rejected

    def test_max_losing_streak_rejects(self):
        metrics = {"longest_losing_streak": "10", "trade_count": 10}
        is_rejected, reasons = check_rejections(metrics, 5)
        assert is_rejected
        assert any("LONG_LOSE_STREAK" in r for r in reasons)

    def test_max_losing_streak_accepts(self):
        metrics = {"longest_losing_streak": "3", "trade_count": 10}
        is_rejected, reasons = check_rejections(metrics, 5)
        assert not is_rejected

    def test_min_sessions_rejects(self):
        metrics = {"trade_count": 10}
        is_rejected, reasons = check_rejections(metrics, 1)
        assert is_rejected
        assert any("INSUFFICIENT_SESSIONS" in r for r in reasons)

    def test_min_sessions_accepts(self):
        metrics = {"trade_count": 10}
        is_rejected, reasons = check_rejections(metrics, 5)
        assert not is_rejected


class TestMultipleRules:
    def test_multiple_rules_fire(self):
        metrics = {"trade_count": 2, "win_rate": "0.1", "longest_losing_streak": "10"}
        is_rejected, reasons = check_rejections(metrics, 1)
        assert is_rejected
        assert len(reasons) >= 3

    def test_none_fire_with_good_data(self):
        metrics = {"trade_count": 20, "max_drawdown": "30", "net_pnl": "100", "win_rate": "0.6", "longest_losing_streak": "3"}
        is_rejected, reasons = check_rejections(metrics, 5)
        assert not is_rejected
        assert reasons == ()
