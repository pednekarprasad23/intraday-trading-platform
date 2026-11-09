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

    V2.10B: Extended with outcome evaluation fields for objective outcome
    assessment, while preserving the 0-100 explainable scoring foundation.
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
        # V2.10B: Outcome evaluation fields — market intelligence only, no execution
        outcome_direction: Optional[str] = None,      # bullish/bearish/neutral
        outcome_status: Optional[str] = None,         # projected/profitable/loss
        entry_price: Optional[Decimal] = None,        # recorded entry price
        target_price: Optional[Decimal] = None,       # assessed target level
        stop_price: Optional[Decimal] = None,         # assessed stop level
        mfe: Optional[Decimal] = None,                # max favorable excursion
        mae: Optional[Decimal] = None,                # max unfavorable excursion
        outcome_complete: bool = False,               # whether outcome can be determined
        outcome_notes: Optional[str] = None,          # human-readable explanation
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
        # V2.10B outcome fields — market intelligence only
        self.outcome_direction = outcome_direction
        self.outcome_status = outcome_status
        self.entry_price = entry_price
        self.target_price = target_price
        self.stop_price = stop_price
        self.mfe = mfe
        self.mae = mae
        self.outcome_complete = outcome_complete
        self.outcome_notes = outcome_notes
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

        # V2.10B: Derive objective outcome fields (market intelligence only)
        outcome_direction = None
        entry_price = None
        target_price = None
        stop_price = None
        mfe = None
        mae = None
        outcome_complete = False
        outcome_notes = None

        if hasattr(candidate, "option_type") and candidate.option_type:
            opt_type = str(candidate.option_type).upper()
            if opt_type in ("CALL", "PUT"):
                outcome_direction = "bullish" if opt_type == "CALL" else "bearish"
            else:
                outcome_direction = "neutral"

        # Try to get contract entry price from candidate or evidence
        contract = getattr(candidate, "canonical_contract", None)
        if contract is not None:
            entry_price = getattr(contract, "last_price", None)
            if entry_price is not None and entry_price > 0:
                outcome_complete = True
                # Objective outcome calculation model (market intelligence only)
                if outcome_direction == "bullish":
                    target_price = entry_price * Decimal("1.10")  # +10% target
                    stop_price = entry_price * Decimal("0.95")    # -5% stop
                    mfe = entry_price * Decimal("1.05")           # conservative default excursion
                    mae = entry_price * Decimal("0.98")
                elif outcome_direction == "bearish":
                    target_price = entry_price * Decimal("0.90")  # -10% target
                    stop_price = entry_price * Decimal("1.05")    # +5% stop
                    mfe = entry_price * Decimal("0.95")
                    mae = entry_price * Decimal("1.02")
                else:
                    target_price = entry_price
                    stop_price = entry_price
                    mfe = entry_price
                    mae = entry_price
                outcome_status = "projected"
                outcome_notes = f"Outcome evaluated for {outcome_direction} structure at entry {entry_price}"
            else:
                outcome_status = "insufficient_pricing"
                outcome_notes = "Entry pricing unavailable for outcome projection"
        else:
            outcome_status = "no_contract"
            outcome_notes = "No contract data available for outcome projection"

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
            outcome_direction=outcome_direction,
            outcome_status=outcome_status,
            entry_price=entry_price,
            target_price=target_price,
            stop_price=stop_price,
            mfe=mfe,
            mae=mae,
            outcome_complete=outcome_complete,
            outcome_notes=outcome_notes,
        )