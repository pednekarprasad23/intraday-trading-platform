"""Missed Opportunity Analysis — V2.10C.

Analyzes historical replay runs and evaluation results to identify qualifying
or high-scoring opportunities that were filtered out, unselected, or missed
due to conservative thresholds.

Market intelligence and research only.
ZERO execution coupling. ZERO broker coupling. ZERO paper trading coupling.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, List, Optional

from app.analysis.opportunity_engine import OpportunityResult


@dataclass
class MissedOpportunityRecord:
    """Structured intelligence for a single missed or filtered opportunity."""

    opportunity_id: str
    candidate_id: str
    evaluated_at: str
    overall_score: Decimal
    completeness: str
    miss_reason: str
    evidence_summary: Dict[str, Any] = field(default_factory=dict)
    notes: Optional[str] = None


class MissedOpportunityAnalyzer:
    """Analyzes opportunity evaluations to surface missed setups or strict filter rejections."""

    engine_id = "missed-opportunity-analyzer"
    engine_version = "1.0.0"

    def __init__(self, score_threshold: Decimal = Decimal("60.0")) -> None:
        self.score_threshold = score_threshold

    def analyze_misses(
        self,
        opportunities: List[OpportunityResult],
        selected_candidate_ids: Set[str] | list[str],
    ) -> List[MissedOpportunityRecord]:
        """Identify high-scoring opportunities that were not selected."""
        selected_set = set(selected_candidate_ids)
        missed_records: List[MissedOpportunityRecord] = []

        for opp in opportunities:
            # If opportunity has strong score but was not selected
            if opp.overall_score >= self.score_threshold and opp.candidate_id not in selected_set:
                missing_engines = opp.evidence.get("missing_engines", [])
                if missing_engines:
                    miss_reason = f"Missing data from engines: {', '.join(missing_engines)}"
                elif not opp.ranking_eligible:
                    miss_reason = "Ineligible for ranking despite score threshold"
                else:
                    miss_reason = "Filtered out by selection threshold or portfolio constraints"

                record = MissedOpportunityRecord(
                    opportunity_id=opp.opportunity_id,
                    candidate_id=opp.candidate_id,
                    evaluated_at=opp.evaluated_at,
                    overall_score=opp.overall_score,
                    completeness=opp.completeness,
                    miss_reason=miss_reason,
                    evidence_summary=opp.evidence,
                    notes=opp.notes,
                )
                missed_records.append(record)

        return missed_records
