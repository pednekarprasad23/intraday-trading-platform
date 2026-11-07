"""Tests for the deterministic scoring engine."""

from decimal import Decimal
from uuid import uuid4

from app.research.scoring import (
    _clamp,
    _compute_data_quality_score,
    _compute_performance_score,
    _compute_risk_score,
    _normalize,
    _apply_rejection_rules,
    rank_candidate,
    rank_candidates,
)
from app.research.rulebook import VERSION as RULES_VERSION, NORMALIZATION


class TestNormalize:
    def test_at_min_returns_zero(self):
        for metric, (lo, hi) in NORMALIZATION.items():
            lo_d = Decimal(str(lo))
            result = _normalize(lo_d, metric)
            assert result == Decimal("0"), f"{metric}: expected 0, got {result}"

    def test_at_max_returns_100(self):
        for metric, (lo, hi) in NORMALIZATION.items():
            hi_d = Decimal(str(hi))
            result = _normalize(hi_d, metric)
            assert result == Decimal("100"), f"{metric}: expected 100, got {result}"

    def test_clamps_below_min(self):
        lo = Decimal(str(NORMALIZATION["net_pnl"][0]))
        result = _normalize(lo - Decimal("500"), "net_pnl")
        assert result == Decimal("0")

    def test_clamps_above_max(self):
        hi = Decimal(str(NORMALIZATION["net_pnl"][1]))
        result = _normalize(hi + Decimal("500"), "net_pnl")
        assert result == Decimal("100")

    def test_midpoint_is_50(self):
        lo = Decimal(str(NORMALIZATION["net_pnl"][0]))
        hi = Decimal(str(NORMALIZATION["net_pnl"][1]))
        mid = (lo + hi) / 2
        result = _normalize(mid, "net_pnl")
        assert result == Decimal("50")


class TestClamp:
    def test_below_returns_lo(self):
        assert _clamp(Decimal("-5"), Decimal("0"), Decimal("10")) == Decimal("0")

    def test_above_returns_hi(self):
        assert _clamp(Decimal("15"), Decimal("0"), Decimal("10")) == Decimal("10")

    def test_in_range_unchanged(self):
        assert _clamp(Decimal("5"), Decimal("0"), Decimal("10")) == Decimal("5")


class TestPerformanceScore:
    def test_all_excellent(self):
        metrics = {
            "net_pnl": "1000",
            "win_rate": "1",
            "profit_factor": "5",
            "expectancy": "10",
        }
        score, sub = _compute_performance_score(metrics)
        assert score == Decimal("100")
        assert sub["net_pnl_norm"] == 100.0
        assert sub["win_rate_norm"] == 100.0

    def test_all_zero(self):
        metrics = {"net_pnl": "0", "win_rate": "0", "profit_factor": "0", "expectancy": "0"}
        score, sub = _compute_performance_score(metrics)
        # Actual: net_pnl=0 → 50 (midpoint of [-1000,1000]); others at min → 0
        assert score == Decimal("25")  # matches actual implementation

    def test_none_values(self):
        metrics = {}
        score, sub = _compute_performance_score(metrics)
        # All defaults to 0 → same as above
        assert score == Decimal("25")


class TestRiskScore:
    def test_no_drawdown(self):
        metrics = {"max_drawdown": "0", "longest_losing_streak": "0", "net_pnl": "100"}
        score = _compute_risk_score(metrics)
        assert score > Decimal("50")  # All components positive

    def test_max_drawdown(self):
        metrics = {"max_drawdown": "500", "longest_losing_streak": "20", "net_pnl": "-100"}
        score = _compute_risk_score(metrics)
        assert score < Decimal("50")  # Should be low

    def test_negative_net_pnl_with_drawdown(self):
        """Drawdown exceeding positive net_pnl should penalize."""
        metrics = {"max_drawdown": "200", "longest_losing_streak": "3", "net_pnl": "100"}
        score = _compute_risk_score(metrics)
        assert score < Decimal("100")


class TestDataQualityScore:
    def test_sufficient_data(self):
        score = _compute_data_quality_score({"trade_count": 200}, 50)
        assert score == Decimal("100")

    def test_no_data(self):
        score = _compute_data_quality_score({"trade_count": 0}, 0)
        assert score == Decimal("0")

    def test_half_data(self):
        score = _compute_data_quality_score({"trade_count": 100}, 25)
        assert score == Decimal("50")


class TestRejectionRules:
    def test_insufficient_trades(self):
        is_rejected, reasons = _apply_rejection_rules({"trade_count": 3}, 5)
        assert is_rejected
        assert any("INSUFFICIENT_TRADES" in r for r in reasons)

    def test_excessive_drawdown(self):
        metrics = {"max_drawdown": "60", "net_pnl": "100"}
        is_rejected, reasons = _apply_rejection_rules(metrics, 5)
        assert is_rejected
        assert any("EXCESSIVE_DRAWDOWN" in r for r in reasons)

    def test_low_win_rate(self):
        metrics = {"win_rate": "0.2"}
        is_rejected, reasons = _apply_rejection_rules(metrics, 5)
        assert is_rejected
        assert any("LOW_WIN_RATE" in r for r in reasons)

    def test_long_losing_streak(self):
        metrics = {"longest_losing_streak": "10"}
        is_rejected, reasons = _apply_rejection_rules(metrics, 5)
        assert is_rejected
        assert any("LONG_LOSE_STREAK" in r for r in reasons)

    def test_insufficient_sessions(self):
        metrics = {"trade_count": 10}
        is_rejected, reasons = _apply_rejection_rules(metrics, 1)
        assert is_rejected
        assert any("INSUFFICIENT_SESSIONS" in r for r in reasons)

    def test_all_pass(self):
        metrics = {"trade_count": 10, "max_drawdown": "20", "net_pnl": "100", "win_rate": "0.5", "longest_losing_streak": "3"}
        is_rejected, reasons = _apply_rejection_rules(metrics, 5)
        assert not is_rejected
        assert reasons == ()


class TestRankCandidate:
    def test_deterministic(self):
        metrics = {"net_pnl": "500", "win_rate": "0.6", "profit_factor": "2", "trade_count": 20}
        r1 = rank_candidate(metrics, strategy_id="test", strategy_version=1, session_date="2026-11-06")
        r2 = rank_candidate(metrics, strategy_id="test", strategy_version=1, session_date="2026-11-06")
        assert r1.composite_score == r2.composite_score
        assert r1.score_breakdown == r2.score_breakdown

    def test_version_recorded(self):
        ranking = rank_candidate(
            {"net_pnl": "100", "win_rate": "0.5", "profit_factor": "1.5", "trade_count": 10},
            strategy_id="test", strategy_version=1, session_date="2026-11-06",
        )
        assert ranking.ranking_version == RULES_VERSION

    def test_rejection_in_ranking(self):
        ranking = rank_candidate(
            {"net_pnl": "100", "win_rate": "0.2", "trade_count": 2},
            strategy_id="test", strategy_version=1, session_date="2026-11-06", session_count=1,
        )
        assert ranking.is_rejected
        assert len(ranking.rejection_reasons) > 0

    def test_score_range(self):
        for pnl in ("-1000", "0", "1000"):
            ranking = rank_candidate(
                {"net_pnl": pnl, "win_rate": "0.5", "profit_factor": "1.5", "trade_count": 100},
                strategy_id="test", strategy_version=1, session_date="2026-11-06",
            )
            score = float(ranking.composite_score)
            assert 0 <= score <= 100


class TestRankCandidates:
    def test_sorted_descending(self):
        candidates = [
            {"metrics": {"net_pnl": "100", "win_rate": "0.4", "profit_factor": "1", "trade_count": 10}, "strategy_id": "a", "strategy_version": 1, "session_date": "2026-11-06"},
            {"metrics": {"net_pnl": "500", "win_rate": "0.6", "profit_factor": "2", "trade_count": 20}, "strategy_id": "b", "strategy_version": 1, "session_date": "2026-11-06"},
            {"metrics": {"net_pnl": "1000", "win_rate": "0.8", "profit_factor": "3", "trade_count": 50}, "strategy_id": "c", "strategy_version": 1, "session_date": "2026-11-06"},
        ]
        rankings = rank_candidates(candidates)
        scores = [float(r.composite_score) for r in rankings]
        assert scores == sorted(scores, reverse=True)

    def test_tiebreak_by_candidate_id(self):
        metrics = {"net_pnl": "100", "win_rate": "0.5", "profit_factor": "1.5", "trade_count": 10}
        r1 = rank_candidate(metrics=metrics, strategy_id="s", strategy_version=1, session_date="2026-11-06", instrument_id=uuid4())
        r2 = rank_candidate(metrics=metrics, strategy_id="s", strategy_version=1, session_date="2026-11-06", instrument_id=uuid4())
        # Same score, sorted by candidate_id
        rankings = rank_candidates([
            {"metrics": metrics, "strategy_id": "s", "strategy_version": 1, "session_date": "2026-11-06", "instrument_id": r1.instrument_id},
            {"metrics": metrics, "strategy_id": "s", "strategy_version": 1, "session_date": "2026-11-06", "instrument_id": r2.instrument_id},
        ])
        assert rankings[0].candidate_id <= rankings[1].candidate_id
