"""Deterministic commentary generation for rankings.

Template-based by default.  An optional LLM hook can be wired in
later.  Commentary is strictly informational and never alters risk
decisions.
"""

from __future__ import annotations

from app.research.scoring import Ranking


def generate(ranking: Ranking) -> str:
    """Template-based deterministic commentary."""
    parts: list[str] = []

    parts.append("RESEARCH ONLY / SIMULATED / NO BROKER ORDER")
    parts.append("")
    parts.append(f"Composite Score: {ranking.composite_score}/100")

    breakdown = ranking.score_breakdown
    strongest = max(breakdown, key=breakdown.get)  # type: ignore[arg-type]
    weakest = min(breakdown, key=breakdown.get)  # type: ignore[arg-type]
    parts.append(f"Strongest component: {strongest} ({breakdown[strongest]:.1f})")
    parts.append(f"Weakest component: {weakest} ({breakdown[weakest]:.1f})")
    parts.append("")

    if ranking.is_rejected:
        parts.append("REJECTED:")
        for reason in ranking.rejection_reasons:
            parts.append(f"  - {reason}")
        parts.append("")
        parts.append("This candidate does not meet minimum quality thresholds.")
    else:
        parts.append("Status: Not rejected")
    parts.append("")

    sub = ranking.sub_scores
    if "win_rate_norm" in sub:
        wr_pct = float(sub["win_rate_norm"]) / 100 * 100
        parts.append(f"Win rate (normalized): {wr_pct:.1f}%")
    if "profit_factor_norm" in sub:
        parts.append(f"Profit factor (normalized): {float(sub['profit_factor_norm']):.1f}/100")
    parts.append("")

    evidence = ranking.evidence
    if evidence.get("metrics"):
        m = evidence["metrics"]
        parts.append(f"Trades: {m.get('trade_count', 'N/A')}, Net P&L: {m.get('net_pnl', 'N/A')}")

    return "\n".join(parts)


def generate_with_llm(ranking: Ranking, llm_client=None) -> str:
    """Generate commentary with optional LLM augmentation.

    Falls back to template-only on LLM failure.
    """
    template = generate(ranking)
    if llm_client is None:
        return template
    try:
        llm_text = _call_llm(ranking, llm_client)
        if llm_text:
            return (
                f"{template}\n\n"
                "[AI Commentary -- informational only, not a trading recommendation]\n"
                f"{llm_text}"
            )
    except Exception:
        pass
    return template


def _call_llm(ranking: Ranking, llm_client) -> str | None:
    prompt = (
        f"Analyze this research-only backtest candidate:\n"
        f"Score: {ranking.composite_score}/100\n"
        f"Breakdown: {ranking.score_breakdown}\n"
        f"Rejected: {ranking.is_rejected}\n"
        f"Evidence: {ranking.evidence}\n"
        f"Provide a brief commentary. Never recommend trading actions."
    )
    return llm_client.generate(prompt)
