"""Tests for template commentary generation."""

from decimal import Decimal
from uuid import uuid4

from app.research.commentary import generate
from app.research.scoring import rank_candidate


class TestCommentary:
    def test_includes_research_label(self):
        ranking = _good_ranking()
        text = generate(ranking)
        assert "RESEARCH ONLY / SIMULATED / NO BROKER ORDER" in text

    def test_shows_composite_score(self):
        ranking = _good_ranking()
        text = generate(ranking)
        assert f"{ranking.composite_score}/100" in text

    def test_shows_strongest_weakest(self):
        ranking = _good_ranking()
        text = generate(ranking)
        # Text should contain the strongest and weakest component names
        assert "Strongest component:" in text
        assert "Weakest component:" in text

    def test_shows_rejection_reasons(self):
        ranking = _rejected_ranking()
        text = generate(ranking)
        assert "REJECTED:" in text
        for reason in ranking.rejection_reasons:
            assert reason in text

    def test_no_trading_recommendation(self):
        ranking = _good_ranking()
        text = generate(ranking)
        # Check for imperative trading language, not the word "trades" in data display
        imperative_phrases = ["buy ", "buy\n", "sell ", "sell\n", "enter ", "exit ",
                              "should buy", "should sell", "you should", "you must"]
        for phrase in imperative_phrases:
            assert phrase not in text.lower(), f"Found imperative phrase: {phrase}"

    def test_includes_trade_count(self):
        ranking = _good_ranking()
        text = generate(ranking)
        assert "Trades:" in text or "trade_count" in text


def _good_ranking():
    return rank_candidate(
        {"net_pnl": "500", "win_rate": "0.6", "profit_factor": "2", "max_drawdown": "50", "longest_losing_streak": "3", "trade_count": 20},
        strategy_id="test", strategy_version=1, session_date="2026-11-06",
        instrument_id=uuid4(),
        evidence={"metrics": {"net_pnl": "500", "trade_count": 20}},
    )


def _rejected_ranking():
    return rank_candidate(
        {"net_pnl": "100", "win_rate": "0.2", "trade_count": 2},
        strategy_id="test", strategy_version=1, session_date="2026-11-06",
        instrument_id=uuid4(), session_count=1,
    )
