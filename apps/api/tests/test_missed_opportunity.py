"""Unit tests for V2.10C Missed Opportunity Analysis."""

from __future__ import annotations

from decimal import Decimal
import pytest

from app.analysis.opportunity_engine import OpportunityEngine, OpportunityResult
from app.analysis.missed_opportunity import MissedOpportunityAnalyzer, MissedOpportunityRecord


def _make_opp(score: Decimal = Decimal("85"), eligible: bool = True,
              missing: list[str] | None = None) -> OpportunityResult:
    return OpportunityResult(
        opportunity_id=f"opp-{id}",
        candidate_id="candidate-x",
        evaluated_at="2026-11-09T10:00:00+00:00",
        engine_versions={},
        overall_score=score,
        component_scores={},
        evidence={
            "missing_engines": missing or [],
            "completeness": "complete" if not missing else "partial",
        },
        completeness="complete" if not missing else "partial",
        ranking_eligible=eligible,
        notes=None,
    )


def test_missed_opportunity_analyzer_identifies_high_score_not_selected():
    """A high-scoring opportunity not in the selected set is flagged as missed."""
    # Create a high-scoring opportunity (overall_score >= threshold)
    opps = [
        _make_opp(score=Decimal("85")),   # not selected candidate
        _make_opp(score=Decimal("95")),   # also not selected
    ]
    selected = ["selected-candidate"]

    analyzer = MissedOpportunityAnalyzer(score_threshold=Decimal("60.0"))
    misses = analyzer.analyze_misses(opps, selected)

    assert len(misses) == 2
    for miss in misses:
        assert miss.miss_reason != "No record created"


def test_missed_opportunity_does_not_flag_low_score():
    """Opportunities below the score threshold are NOT flagged as missed."""
    opps = [
        _make_opp(score=Decimal("30")),
        _make_opp(score=Decimal("50")),
    ]
    analyzer = MissedOpportunityAnalyzer(score_threshold=Decimal("60.0"))
    misses = analyzer.analyze_misses(opps, [])
    assert len(misses) == 0


def test_missed_opportunity_uses_missing_engines_reason():
    """Under ISSUE-1: missing engine data no longer generates a miss reason
    solely from T0 score. Without an OutcomeEvaluation indexed for the candidate,
    the record is classified as insufficient_future_data.

    The analyzer now requires BOTH T0 intelligence AND Objective Future Outcome
    linkage — not just T0 score + non-selection.
    """
    # Under ISSUE-1: no OutcomeEvaluation indexed for candidate -> insufficient_future_data
    # The old "missing engines" miss reason is replaced by lineage-aware outcome checks.
    missing = ["liquidity-quality", "greeks-snapshot"]
    opp = _make_opp(score=Decimal("70"), missing=missing)
    analyzer = MissedOpportunityAnalyzer(score_threshold=Decimal("60.0"))
    # No outcome evaluations provided -> insufficient_future_data classification
    misses = analyzer.analyze_misses([opp], [])
    assert len(misses) == 1
    record = misses[0]
    # Under ISSUE-1: classification should be insufficient_future_data,
    # not a missing-engines reason
    assert record.classification == "insufficient_future_data"


def test_missed_opportunity_records_correct_fields():
    """Missed records preserve structured intelligence fields."""
    opp = _make_opp(score=Decimal("85"))
    analyzer = MissedOpportunityAnalyzer(score_threshold=Decimal("60.0"))
    misses = analyzer.analyze_misses([opp], [])
    record = misses[0]
    assert isinstance(record, MissedOpportunityRecord)
    assert record.opportunity_id == opp.opportunity_id
    assert record.candidate_id == opp.candidate_id
    assert record.overall_score == opp.overall_score
    assert record.evidence_summary == opp.evidence
    assert record.notes == opp.notes


def test_missed_opportunity_zero_execution_coupling():
    """Verify missed opportunity module has zero execution/broker imports."""
    import ast
    mod_file = __file__
    with open(mod_file, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=mod_file)
    forbidden_modules = {
        "paper_trading", "broker", "execution", "order", "position", "signal",
        "app.paper_trading", "app.broker",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                for forbidden in forbidden_modules:
                    assert forbidden not in alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            for forbidden in forbidden_modules:
                assert forbidden not in node.module
