"""Deterministic Opportunity Ranking Foundation — V2.9G.

Ranks OpportunityResults deterministically based on:
- ranking_eligible status
- overall_score (descending)
- completeness priority (complete > partial > insufficient)
- candidate_id (stable tie-breaking)

Maintains ZERO execution coupling and zero broker/paper imports.
"""
from __future__ import annotations

from typing import List, Sequence

from app.analysis.opportunity_engine import OpportunityResult


class OpportunityRanker:
    """Deterministic opportunity ranker with stable tie-breaking."""

    @staticmethod
    def rank(opportunities: Sequence[OpportunityResult]) -> List[OpportunityResult]:
        """Rank a sequence of OpportunityResults deterministically.

        Rules:
        1. Only ranking_eligible=True opportunities are ranked at the top.
           Ineligible ones are placed at the bottom.
        2. Sorted by overall_score descending.
        3. Sorted by completeness priority ('complete' > 'partial' > 'insufficient').
        4. Stable tie-breaking by candidate_id ascending for absolute determinism.
        """
        completeness_priority = {
            "complete": 3,
            "partial": 2,
            "insufficient": 1,
        }

        def sort_key(opp: OpportunityResult):
            # Ineligible goes last (0 vs 1)
            eligibility_score = 1 if opp.ranking_eligible else 0
            comp_score = completeness_priority.get(opp.completeness, 0)
            score = float(opp.overall_score)
            # Tie breaker: candidate_id ascending (using negative ord or sorting string)
            # Python sorting handles string tuples naturally:
            # (eligibility, overall_score, completeness_priority, -candidate_id or string reverse)
            # To sort candidate_id ascending as tie-breaker when scores are equal:
            # We want higher score first (-score), higher eligibility first (-eligibility_score),
            # higher completeness first (-comp_score), but candidate_id ascending.
            return (
                -eligibility_score,
                -score,
                -comp_score,
                opp.candidate_id,
            )

        return sorted(opportunities, key=sort_key)
