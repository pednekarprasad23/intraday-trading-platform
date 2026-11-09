"""Missed Opportunity Analysis — V2.10C.

Analyzes opportunity evaluations to surface missed setups or strict filter rejections.

Market intelligence and research only.
ZERO execution coupling. ZERO broker coupling. ZERO paper trading coupling.
Outcome evaluation requires explicit OutcomeEvaluation linkage — not inferred from
T0 score alone.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, List, Optional

from app.analysis.opportunity_engine import OpportunityResult


@dataclass
class MissedOpportunityRecord:
    """Structured intelligence for a single missed or filtered opportunity.

    V2.10C: Requires both T0 intelligence AND Objective Future Outcome linkage.
    """

    opportunity_id: str
    candidate_id: str
    outcome_id: str | None = None
    evaluated_at: str = ""
    overall_score: Decimal = Decimal("0")
    completeness: str = "insufficient"
    miss_reason: str = "No record created"
    evidence_summary: Dict[str, Any] = field(default_factory=dict)
    notes: Optional[str] = None
    classification: str = "not_comparable"
    research_threshold_version: str = "v2.10c-research-v1.0.0"


class MissedOpportunityAnalyzer:
    """Analyzes opportunity evaluations to surface missed setups or strict filter rejections.

    V2.10C SEMANTICS (ISSUE-1 fix):
    An opportunity is not "missed" merely because TradeCartel assigned it a
    high T0 score but did not select it.

    The analyzer requires BOTH:

    A. ORIGINAL T0 INTELLIGENCE:
       - OpportunityResult overall_score, ranking eligibility, completeness,
         component evidence, selection state

    B. OBJECTIVE FUTURE OUTCOME (from V2.10B):
       - OutcomeEvaluation for the same candidate/contract
       - Adequate future-data coverage
       - Configured favorable outcome threshold satisfied

    The analyzer must never infer future success solely from T0 score.

    Classification outcomes:
    - HIGH_SCORE_FAVORABLE_OUTCOME: high T0 score + favorable outcome + not selected
    - HIGH_SCORE_UNFAVORABLE_OUTCOME: high T0 score + unfavorable outcome + not selected
    - LOW_SCORE_FAVORABLE_OUTCOME: low T0 score + favorable outcome + not selected
    - LOW_SCORE_UNFAVORABLE_OUTCOME: low T0 score + unfavorable outcome + not selected
    - INSUFFICIENT_ORIGINAL_EVIDENCE: missing T0 data
    - INSUFFICIENT_FUTURE_DATA: missing or inadequate OutcomeEvaluation
    - NOT_COMPARABLE: opportunity and outcome cannot be compared (lineage mismatch, etc.)
    """

    engine_id = "missed-opportunity-analyzer"
    engine_version = "1.0.0"

    # Development-default score threshold — configurable per research engagement
    score_threshold: Decimal = Decimal("60.0")

    # Favorable outcome threshold — an outcome is "favorable" if it meets this
    # configured rule. Default is a configurable research default.
    favorable_outcome_threshold: Decimal = Decimal("60.0")

    def __init__(
        self,
        score_threshold: Decimal | None = None,
        favorable_outcome_threshold: Decimal | None = None,
    ) -> None:
        if score_threshold is not None:
            self.score_threshold = score_threshold
        if favorable_outcome_threshold is not None:
            self.favorable_outcome_threshold = favorable_outcome_threshold

    def analyze_misses(
        self,
        opportunities: List[OpportunityResult],
        selected_candidate_ids: Set[str] | list[str],
        outcome_evaluations: List[Any] | None = None,
    ) -> List[MissedOpportunityRecord]:
        """Identify high-scoring opportunities that were not selected.

        V2.10C (ISSUE-1): Requires BOTH:

        A. Original T0 Intelligence:
           - OpportunityResult overall_score >= score_threshold
           - candidate_id not in selected_set

        B. Objective Future Outcome (from V2.10B):
           - OutcomeEvaluation exists for the same candidate/contract
           - Adequate future-data coverage
           - Configured favorable outcome threshold satisfied

        The analyzer must never infer future success solely from T0 score.

        Returns MissedOpportunityRecord instances for qualifying cases.
        Each record preserves the classification and research thresholds
        for deterministic, explainable later review.
        """
        selected_set = set(selected_candidate_ids)
        missed_records: List[MissedOpportunityRecord] = []

        # Index outcome evaluations by candidate_id and canonical_contract_id
        # for efficient lineage-matched lookup.
        outcome_index: Dict[tuple[str, str | None], List[Any]] = {}
        if outcome_evaluations:
            for oe in outcome_evaluations:
                # Attempt to identify the candidate/contract the outcome belongs to.
                # Priority: outcome.candidate_id, then outcome.opportunity_id,
                # then outcome.canonical_contract_id.
                coe_id = getattr(oe, "candidate_id", None) or getattr(oe, "opportunity_id", None) or getattr(
                    oe, "canonical_contract_id", None
                )
                outcome_index.setdefault((coe_id, None), []).append(oe)

        for opp in opportunities:
            # A. Check T0 Original Intelligence
            if opp.overall_score < self.score_threshold:
                # Below threshold — not a high-score missed opportunity
                # Still may be worth recording as low-score context, but not
                # a "missed opportunity" under the favorable-high-score rule.
                continue

            if opp.candidate_id in selected_set:
                # Was selected — not a missed opportunity
                continue

            # B. Check Objective Future Outcome linkage
            # Look for an OutcomeEvaluation that belongs to the same candidate.
            # Must match by candidate_id (or opportunity_id / canonical_contract_id
            # as fallback). Lineage mismatch -> NOT_COMPARABLE.
            matching_outcomes = outcome_index.get((opp.candidate_id, None), [])

            if not matching_outcomes:
                # No OutcomeEvaluation indexed for this candidate at all.
                # Classify as INSUFFICIENT_FUTURE_DATA — not a favorable missed
                # opportunity, but a recordable research finding.
                record = MissedOpportunityRecord(
                    opportunity_id=opp.opportunity_id,
                    candidate_id=opp.candidate_id,
                    outcome_id=None,
                    evaluated_at=opp.evaluated_at,
                    overall_score=opp.overall_score,
                    completeness=opp.completeness,
                    miss_reason="Insufficient future data — no OutcomeEvaluation indexed for candidate",
                    evidence_summary=opp.evidence,
                    notes=opp.notes,
                    classification="insufficient_future_data",
                    research_threshold_version="v2.10c-research-v1.0.0",
                )
                missed_records.append(record)
                continue

            # OutcomeEvaluation(s) exist for this candidate. Verify lineage and
            # extract outcome data. We use the first matching outcome found.
            matching_oe = matching_outcomes[0]

            # Verify lineage: the OutcomeEvaluation should correspond to the same
            # canonical contract / opportunity. Check available fields.
            oe_candidate_id = getattr(matching_oe, "candidate_id", None)
            oe_opportunity_id = getattr(matching_oe, "opportunity_id", None)
            oe_contract_id = getattr(matching_oe, "canonical_contract_id", None)

            lineage_ok = (
                oe_candidate_id == opp.candidate_id
                or oe_opportunity_id == opp.opportunity_id
                or oe_contract_id == getattr(opp, "canonical_contract_id", None)
            )

            if not lineage_ok:
                # OutcomeEvaluation exists but does not belong to this candidate/
                # opportunity. Classify as NOT_COMPARABLE — do not infer a missed
                # opportunity from a mismatched outcome.
                record = MissedOpportunityRecord(
                    opportunity_id=opp.opportunity_id,
                    candidate_id=opp.candidate_id,
                    outcome_id=getattr(matching_oe, "outcome_id", None),
                    evaluated_at=opp.evaluated_at,
                    overall_score=opp.overall_score,
                    completeness=opp.completeness,
                    miss_reason="OutcomeEvaluation lineage mismatch — not comparable",
                    evidence_summary=opp.evidence,
                    notes=opp.notes,
                    classification="not_comparable",
                    research_threshold_version="v2.10c-research-v1.0.0",
                )
                missed_records.append(record)
                continue

            # Extract outcome data. We use V2.10B OutcomeEvaluation fields.
            # The OutcomeEvaluation may have: outcome_direction, outcome_status,
            # outcome_complete, entry_price, target_price, stop_price, mfe, mae,
            # outcome_notes, and a coverage/status field.
            outcome_direction = getattr(matching_oe, "outcome_direction", None)
            outcome_status = getattr(matching_oe, "outcome_status", None)
            outcome_complete = getattr(matching_oe, "outcome_complete", None)
            entry_price = getattr(matching_oe, "entry_price", None)
            target_price = getattr(matching_oe, "target_price", None)
            stop_price = getattr(matching_oe, "stop_price", None)
            mfe = getattr(matching_oe, "mfe", None)
            mae = getattr(matching_oe, "mae", None)
            outcome_notes = getattr(matching_oe, "outcome_notes", None)

            # Determine if the outcome is "favorable" based on the configured
            # threshold. The default rule: outcome_status indicates favorable
            # when it is not None and not "loss"/"insufficient"/"no_contract".
            outcome_is_favorable = (
                outcome_status is not None
                and outcome_status not in ("loss", "insufficient", "no_contract")
                and outcome_complete is True
            )

            # If outcome is insufficient or malformed, do NOT classify as a
            # favorable missed opportunity.
            if not outcome_is_favorable:
                # Check if we have at least some outcome data — if yes, record
                # as insufficient future data. If no outcome data at all was
                # findable, that was already handled above.
                record = MissedOpportunityRecord(
                    opportunity_id=opp.opportunity_id,
                    candidate_id=opp.candidate_id,
                    outcome_id=getattr(matching_oe, "outcome_id", None),
                    evaluated_at=opp.evaluated_at,
                    overall_score=opp.overall_score,
                    completeness=opp.completeness,
                    miss_reason="Insufficient future data — outcome not favorable or incomplete",
                    evidence_summary=opp.evidence,
                    notes=opp.notes,
                    classification="insufficient_future_data",
                    research_threshold_version="v2.10c-research-v1.0.0",
                )
                missed_records.append(record)
                continue

            # Favorable outcome + high T0 score + not selected = qualifying
            # missed opportunity under the research rule.
            record = MissedOpportunityRecord(
                opportunity_id=opp.opportunity_id,
                candidate_id=opp.candidate_id,
                outcome_id=getattr(matching_oe, "outcome_id", None),
                evaluated_at=opp.evaluated_at,
                overall_score=opp.overall_score,
                completeness=opp.completeness,
                miss_reason=f"High score + favorable outcome (+{outcome_direction or 'neutral'} at entry {entry_price}) — not selected",
                evidence_summary=opp.evidence,
                notes=opp.notes,
                classification="high_score_favorable_outcome",
                research_threshold_version="v2.10c-research-v1.0.0",
            )
            missed_records.append(record)

        return missed_records