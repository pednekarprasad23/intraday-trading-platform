"""Unit tests for V2.9G Opportunity Engine & Ranking Foundation."""

from __future__ import annotations

from decimal import Decimal
import pytest

from app.discovery.scanner import ReferenceTestScanner, ScannerContext, MarketCandidate
from app.discovery.provider import FixtureDiscoveryAdapter
from app.analysis.engine import AnalysisResult
from app.analysis.opportunity_engine import OpportunityEngine, OpportunityResult
from app.analysis.ranking import OpportunityRanker


def create_test_candidate() -> MarketCandidate:
    adapter = FixtureDiscoveryAdapter()
    snapshot = adapter.get_option_chain("NIFTY", "2026-11-26")
    scanner = ReferenceTestScanner()
    candidates = scanner.scan(ScannerContext("test-universe", snapshot))
    return candidates[0]


def test_opportunity_evaluation_complete():
    candidate = create_test_candidate()
    results = {
        "liquidity-quality": AnalysisResult(
            engine_id="liquidity-quality",
            engine_version="1.0.0",
            candidate=candidate,
            analysis_id="lq-1",
            metrics={"spread_percentage": "1.32", "volume": 5000, "open_interest": 12000},
            qualifying=True,
            notes="Liquidity status: healthy",
        ),
        "greeks-snapshot": AnalysisResult(
            engine_id="greeks-snapshot",
            engine_version="1.0.0",
            candidate=candidate,
            analysis_id="g-1",
            metrics={"delta": "-0.45", "gamma": "0.002", "theta": "-12.5", "vega": "25.0"},
            qualifying=True,
            notes="Greeks snapshot observed",
        ),
        "iv-snapshot": AnalysisResult(
            engine_id="iv-snapshot",
            engine_version="1.0.0",
            candidate=candidate,
            analysis_id="iv-1",
            metrics={"implied_volatility": "15.5"},
            qualifying=True,
            notes="IV snapshot observed",
        ),
        "oi-participation": AnalysisResult(
            engine_id="oi-participation",
            engine_version="1.0.0",
            candidate=candidate,
            analysis_id="oi-1",
            metrics={"volume": 5000, "open_interest": 12000, "volume_ratio": "0.4167"},
            qualifying=True,
            notes="OI/participation observed",
        ),
    }

    opp = OpportunityEngine.evaluate(candidate, results)
    assert isinstance(opp, OpportunityResult)
    assert opp.candidate_id == candidate.candidate_id
    assert opp.completeness == "complete"
    assert opp.ranking_eligible is True
    assert opp.overall_score == Decimal("100.00")
    assert len(opp.component_scores) == 4
    assert opp.component_scores["liquidity-quality"] == Decimal("100")


def test_opportunity_evaluation_partial_and_missing():
    candidate = create_test_candidate()
    results = {
        "liquidity-quality": AnalysisResult(
            engine_id="liquidity-quality",
            engine_version="1.0.0",
            candidate=candidate,
            analysis_id="lq-1",
            metrics={"spread_percentage": "1.32"},
            qualifying=True,
            notes="healthy",
        ),
        "iv-snapshot": AnalysisResult(
            engine_id="iv-snapshot",
            engine_version="1.0.0",
            candidate=candidate,
            analysis_id="iv-1",
            metrics={"implied_volatility": "15.5"},
            qualifying=True,
            notes="observed",
        ),
    }

    opp = OpportunityEngine.evaluate(candidate, results)
    assert opp.completeness == "partial"
    assert "greeks-snapshot" in opp.evidence["missing_engines"]
    assert "oi-participation" in opp.evidence["missing_engines"]
    assert opp.component_scores["greeks-snapshot"] == Decimal("0")
    assert opp.overall_score == Decimal("100.00")


def test_opportunity_ranking_determinism():
    c1 = create_test_candidate()

    opp1 = OpportunityResult(
        opportunity_id="op-1",
        candidate_id="CANDIDATE-A",
        evaluated_at="2026-11-09T00:00:00Z",
        engine_versions={},
        overall_score=Decimal("80.00"),
        component_scores={},
        evidence={},
        completeness="complete",
        ranking_eligible=True,
    )
    opp2 = OpportunityResult(
        opportunity_id="op-2",
        candidate_id="CANDIDATE-B",
        evaluated_at="2026-11-09T00:00:00Z",
        engine_versions={},
        overall_score=Decimal("95.00"),
        component_scores={},
        evidence={},
        completeness="complete",
        ranking_eligible=True,
    )
    opp3 = OpportunityResult(
        opportunity_id="op-3",
        candidate_id="CANDIDATE-C",
        evaluated_at="2026-11-09T00:00:00Z",
        engine_versions={},
        overall_score=Decimal("80.00"),
        component_scores={},
        evidence={},
        completeness="complete",
        ranking_eligible=True,
    )

    ranked = OpportunityRanker.rank([opp1, opp2, opp3])
    assert ranked[0].candidate_id == "CANDIDATE-B"
    assert ranked[1].candidate_id == "CANDIDATE-A"
    assert ranked[2].candidate_id == "CANDIDATE-C"


def test_zero_execution_dependency():
    """Verify opportunity engine maintains zero execution/broker/paper imports."""
    import ast
    from app.analysis import opportunity_engine, ranking

    modules_to_check = [opportunity_engine, ranking]
    forbidden_modules = {
        "paper_trading",
        "broker",
        "execution",
        "order",
        "position",
        "signal",
        "app.paper_trading",
        "app.broker",
    }

    for mod in modules_to_check:
        mod_file = mod.__file__
        with open(mod_file, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=mod_file)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        for forbidden in forbidden_modules:
                            assert forbidden not in alias.name, (
                                f"Forbidden import '{alias.name}' found in {mod_file}"
                            )
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        for forbidden in forbidden_modules:
                            assert forbidden not in node.module, (
                                f"Forbidden import from '{node.module}' found in {mod_file}"
                            )
