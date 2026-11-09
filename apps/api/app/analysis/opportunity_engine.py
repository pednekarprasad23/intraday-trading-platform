"""Opportunity Engine — V2.9G.

Combines independent AnalysisResults for a MarketCandidate into a single
OpportunityResult with explainable scoring and deterministic ranking.

This is the OPPORTUNITY ENGINE + SCORING/RANKING FOUNDATION only.
No execution, no recommendations, no trade approval.

DO NOT:
- Create BUY/SELL semantics
- Create execution directives
- Combine engine results into trade approval
- Infer directional overreach from isolated snapshots

DO:
- Provide explainable scoring based on genuinely available evidence
- Represent missing data completeness transparently
- Support deterministic ranking with tie-breaking
- Maintain zero imports into PAPER/broker/execution modules
"""
from __future__ import annotations

from decimal import Decimal
from hashlib import sha256
from typing import Any, Dict, Optional

from datetime import datetime, timezone

from app.analysis.engine import AnalysisEngine, AnalysisResult
from app.discovery.provider import NormalizedOptionContract


class OpportunityResult:
    """Result of opportunity evaluation — market intelligence only.

    NOT a trade instruction, order, or execution directive.
    """

    def __init__(
        self,
        opportunity_id: str,
        candidate_id: str,
        evaluated_at: str,
        engine_versions: Dict[str, str],
        overall_score: Decimal,
        component_scores: Dict[str, Decimal],
        evidence: Dict[str, Any],
        completeness: str,
        ranking_eligible: bool,
        notes: Optional[str] = None,
    ):
        self.opportunity_id = opportunity_id
        self.candidate_id = candidate_id
        self.evaluated_at = evaluated_at
        self.engine_versions = engine_versions
        self.overall_score = overall_score
        self.component_scores = component_scores
        self.evidence = evidence
        self.completeness = completeness
        self.ranking_eligible = ranking_eligible
        self.notes = notes

    def __repr__(self) -> str:
        return (
            f"<OpportunityResult id={self.opportunity_id} "
            f"candidate={self.candidate_id} score={self.overall_score} "
            f"eligible={self.ranking_eligible}>"
        )

    def __str__(self) -> str:
        return (
            f"OpportunityResult(opportunity_id={self.opportunity_id}, "
            f"candidate={self.candidate_id}, "
            f"overall_score={str(self.overall_score)}, "
            f"ranking_eligible={self.ranking_eligible})"
        )


class OpportunityEngine(AnalysisEngine):
    """Combines independent AnalysisResults for a MarketCandidate.

    Consumes:
      - ONE MarketCandidate
      - multiple AnalysisResults belonging to that candidate

    Produces:
      - ONE OpportunityResult with explainable scoring
      - Deterministic ranking eligibility

    Critical semantic rules:
      - qualifying AnalysisResults are NOT trade votes
      - overall_score reflects ONLY evidence genuinely available today
      - Missing data is explicitly represented (not silently zeroed)
      - Component scores must be explainable through overall_score
      - CALL/PUT remain analytically neutral
    """

    engine_id = "opportunity"
    engine_version = "1.0.0"

    # Development-default weighting — configurable, testable
    _LIQUIDITY_WEIGHT = Decimal("0.25")
    _GREEKS_WEIGHT = Decimal("0.25")
    _IV_WEIGHT = Decimal("0.25")
    _OI_PARTICIPATION_WEIGHT = Decimal("0.25")

    # Overall score scale: 0-100 as per V2.9G contract
    _MAX_SCORE = Decimal("100")

    def analyze(self, context: Any) -> AnalysisResult:  # noqa: F821
        """Not implemented — OpportunityEngine evaluates multiple results."""
        raise NotImplementedError(
            "Use OpportunityEngine.evaluate() instead of analyze()."
        )

    @staticmethod
    def evaluate(
        candidate: Any,
        analysis_results: dict[str, AnalysisResult],
    ) -> OpportunityResult:
        """Evaluate a candidate's combined opportunity profile."""
        engine_versions: dict[str, str] = {}
        component_scores: dict[str, Decimal] = {}
        evidence: dict[str, Any] = {}
        missing_engines: list[str] = []
        total_weight = Decimal("0")
        weighted_score = Decimal("0")

        engine_contributions = {
            "liquidity-quality": {
                "weight": OpportunityEngine._LIQUIDITY_WEIGHT,
            },
            "greeks-snapshot": {
                "weight": OpportunityEngine._GREEKS_WEIGHT,
            },
            "iv-snapshot": {
                "weight": OpportunityEngine._IV_WEIGHT,
            },
            "oi-participation": {
                "weight": OpportunityEngine._OI_PARTICIPATION_WEIGHT,
            },
        }

        for engine_id, contrib in engine_contributions.items():
            result = analysis_results.get(engine_id)

            if result is None:
                missing_engines.append(engine_id)
                component_scores[engine_id] = Decimal("0")
                continue

            engine_versions[engine_id] = result.engine_version
            is_qualifying = result.qualifying
            metrics = result.metrics or {}

            if engine_id == "liquidity-quality":
                if is_qualifying:
                    component_scores[engine_id] = OpportunityEngine._MAX_SCORE
                else:
                    spread_pct = Decimal(metrics.get("spread_percentage", "0"))
                    if spread_pct > 0:
                        component_scores[engine_id] = OpportunityEngine._MAX_SCORE * Decimal("0.5")
                    else:
                        component_scores[engine_id] = Decimal("0")
                        missing_engines.append(engine_id)

            elif engine_id == "greeks-snapshot":
                if is_qualifying:
                    component_scores[engine_id] = OpportunityEngine._MAX_SCORE
                else:
                    delta = metrics.get("delta", None) if metrics else None
                    if delta is not None:
                        component_scores[engine_id] = OpportunityEngine._MAX_SCORE * Decimal("0.5")
                    else:
                        component_scores[engine_id] = Decimal("0")
                        missing_engines.append(engine_id)

            elif engine_id == "iv-snapshot":
                if is_qualifying:
                    component_scores[engine_id] = OpportunityEngine._MAX_SCORE
                else:
                    iv_val = metrics.get("implied_volatility", None) if metrics else None
                    if iv_val is not None and Decimal(str(iv_val)) > 0:
                        component_scores[engine_id] = OpportunityEngine._MAX_SCORE * Decimal("0.5")
                    else:
                        component_scores[engine_id] = Decimal("0")
                        missing_engines.append(engine_id)

            elif engine_id == "oi-participation":
                if is_qualifying:
                    component_scores[engine_id] = OpportunityEngine._MAX_SCORE
                else:
                    volume_ratio = Decimal(metrics.get("volume_ratio", "0")) if metrics else Decimal("0")
                    if volume_ratio > 0:
                        component_scores[engine_id] = OpportunityEngine._MAX_SCORE * Decimal("0.5")
                    else:
                        component_scores[engine_id] = Decimal("0")
                        missing_engines.append(engine_id)

            if component_scores[engine_id] > 0:
                total_weight += contrib["weight"]
                weighted_score += component_scores[engine_id] * contrib["weight"]

        total_engines = len(engine_contributions)
        if not missing_engines:
            completeness = "complete"
            ranking_eligible = True
        elif len(missing_engines) < total_engines:
            completeness = "partial"
            ranking_eligible = total_weight > Decimal("0.1")
        else:
            completeness = "insufficient"
            ranking_eligible = False

        if total_weight > 0:
            overall_score = (weighted_score / total_weight).quantize(
                Decimal("0.01"), rounding="ROUND_HALF_UP"
            )
        else:
            overall_score = Decimal("0")

        overall_score = min(overall_score, OpportunityEngine._MAX_SCORE)

        engine_evidence = {}
        for engine_id in engine_contributions:
            result = analysis_results.get(engine_id)
            if result is not None:
                engine_evidence[engine_id] = {
                    "qualifying": result.qualifying,
                    "notes": result.notes,
                }

        evidence = {
            "engine_contributions": engine_evidence,
            "missing_engines": missing_engines,
            "completeness": completeness,
        }

        candidate_id_str = str(getattr(candidate, "candidate_id", "unknown"))
        evaluated_at = datetime.now(timezone.utc).isoformat()
        opportunity_id = sha256(
            f"{candidate_id_str}:{evaluated_at}".encode()
        ).hexdigest()[:16]

        notes_parts = []
        if missing_engines:
            notes_parts.append(f"missing: {', '.join(missing_engines)}")
        if completeness == "partial":
            notes_parts.append("partial evidence — ranking eligible")
        if completeness == "insufficient":
            notes_parts.append("insufficient evidence — not ranking eligible")

        notes = "; ".join(notes_parts) if notes_parts else None

        return OpportunityResult(
            opportunity_id=opportunity_id,
            candidate_id=candidate_id_str,
            evaluated_at=evaluated_at,
            engine_versions=engine_versions,
            overall_score=overall_score,
            component_scores=component_scores,
            evidence=evidence,
            completeness=completeness,
            ranking_eligible=ranking_eligible,
            notes=notes,
        )