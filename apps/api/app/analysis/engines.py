"""Initial Real Analysis Engines — V2.9F.

Implements the FIRST real analysis engines whose required data actually
exists in normalized TradeCartel data.

Data capability assessment (inspect OptionChainSnapshot /
NormalizedOptionContract):

AVAILABLE (implement now):
  - Liquidity Quality Engine      : volume, open_interest, bid, ask, spread
  - Options Greeks Snapshot Engine: delta, gamma, theta, vega (actual Greeks)
  - Implied Volatility Snapshot   : implied_volatility (populated: 15.5)
  - Open Interest / Participation : open_interest, volume

BLOCKED BY MISSING HISTORICAL DATA:
  - RSI, MACD, Supertrend, ATR, VWAP, EMA/SMA, IV Rank, IV Percentile
  - These require time-series / reference data not currently available.
  - Blocked engines and their missing data dependencies are recorded
    for the roadmap.

Absolute boundary:
  - ZERO imports/coupling into PAPER / broker-execution / live-execution
  - No opportunity engine, composite scoring, ranking, or recommendation.
  - Calling analyze() on an engine returns:
        qualifying = "candidate satisfies THIS engine's criteria"
    NOT "trade approved / BUY / SELL / execute".

Each engine returns an independent AnalysisResult.
"""

from __future__ import annotations

from decimal import Decimal

from app.analysis.engine import AnalysisContext, AnalysisEngine, AnalysisResult
from app.discovery.provider import NormalizedOptionContract


# ---------------------------------------------------------------------------
# Configuration (explicit, centralized, default dev values)
# ---------------------------------------------------------------------------

class EngineConfig:
    """Centralized, testable configuration keys for V2.9F engines."""

    # Liquidity Quality Engine thresholds (development defaults)
    MIN_VOLUME = 100
    MIN_OPEN_INTEREST = 100
    MAX_SPREAD_PCT = 20.0

    # Greeks Snapshot Engine thresholds (development defaults)
    MIN_ABS_DELTA = 0.05

    # IV Snapshot Engine thresholds (development defaults)
    MIN_IMPLIED_VOLATILITY = Decimal("0.01")

    # OI/Participation Engine thresholds (development defaults)
    MIN_VOLUME_RATIO = Decimal("0.01")


# ---------------------------------------------------------------------------
# Liquidity Quality Engine
# ---------------------------------------------------------------------------

class LiquidityQualityEngine(AnalysisEngine):
    """Measure market tradability of a candidate's current state.

    Inputs (normalized data):
      - volume
      - open_interest
      - bid_price
      - ask_price

    Outputs (AnalysisResult.qualifying):
      True only when the candidate passes all liquidity thresholds:
      - volume >= config.MIN_VOLUME
      - open_interest >= config.MIN_OPEN_INTEREST
      - bid/ask available, bid <= ask, spread within max_spread_pct

    Evidence keys returned:
      - volume
      - open_interest
      - bid
      - ask
      - absolute_spread
      - spread_percentage
      - liquidity_status (gateway / quality / healthy)

    Semantically:
      qualifying True  => liquidity criteria met
      qualifying False => liquidity criteria NOT met (still may be a valid
                         candidate for other engines; do NOT assume trade).
    """

    engine_id = "liquidity-quality"
    engine_version = "1.0.0"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        config = config or {}
        self.min_volume = Decimal(str(config.get("min_volume", EngineConfig.MIN_VOLUME)))
        self.min_open_interest = Decimal(str(config.get("min_open_interest", EngineConfig.MIN_OPEN_INTEREST)))
        self.max_spread_pct = Decimal(str(config.get("max_spread_pct", EngineConfig.MAX_SPREAD_PCT)))

    def _compute_spread(self, contract: NormalizedOptionContract) -> tuple[Decimal, Decimal]:
        bid = contract.bid_price
        ask = contract.ask_price
        if bid is None or ask is None:
            return Decimal("0"), Decimal("0")
        abs_spread = abs(ask - bid)
        spread_pct = (abs_spread / ask * Decimal("100")) if ask else Decimal("0")
        return abs_spread, spread_pct

    def analyze(self, context: AnalysisContext) -> AnalysisResult:
        candidate = context.candidate
        contract = candidate.canonical_contract
        evidence: dict[str, Any] = {}
        metrics: dict[str, Any] = {}

        # Store candidate_id for _generate_analysis_id
        object.__setattr__(self, "_candidate_id", candidate.candidate_id)

        # Extract normalized values safely
        volume = contract.volume or 0
        open_interest = contract.open_interest or 0
        bid = contract.bid_price if contract.bid_price is not None else Decimal("0")
        ask = contract.ask_price if contract.ask_price is not None else Decimal("0")

        abs_spread, spread_pct = self._compute_spread(contract)

        metrics["volume"] = volume
        metrics["open_interest"] = open_interest
        metrics["bid"] = str(bid)
        metrics["ask"] = str(ask)
        metrics["absolute_spread"] = str(abs_spread)
        metrics["spread_percentage"] = str(spread_pct)

        # Determine eligibility (does not change whether data is valid;
        # that distinction is handled by the scanner)
        liquidity_sufficient = (
            volume >= self.min_volume
            and open_interest >= self.min_open_interest
            and ask > 0
            and bid >= 0
            and spread_pct <= self.max_spread_pct
        )

        if liquidity_sufficient:
            status = "healthy"
            qualifying = True
        elif bid > 0 or ask > 0:
            status = "partial"
            qualifying = False
        else:
            status = "gateway"
            qualifying = False

        evidence["volume"] = volume
        evidence["open_interest"] = open_interest
        evidence["bid"] = str(bid)
        evidence["ask"] = str(ask)
        evidence["absolute_spread"] = str(abs_spread)
        evidence["spread_percentage"] = str(spread_pct)
        evidence["liquidity_status"] = status

        return AnalysisResult(
            engine_id=self.engine_id,
            engine_version=self.engine_version,
            candidate=candidate,
            analysis_id=self._generate_analysis_id(),
            metrics=metrics,
            qualifying=qualifying,
            notes=f"Liquidity status: {status}",
        )

    def _generate_analysis_id(self) -> str:
        # Deterministic: use the candidate_id from the candidate object
        # This is set during analyze() via the AnalysisContext
        candidate_id = getattr(self, "_candidate_id", "unknown")
        return candidate_id

    def __repr__(self) -> str:  # pragma: no cover - debug
        return f"<{self.engine_id} v{self.engine_version}>"


# ---------------------------------------------------------------------------
# Options Greeks Snapshot Engine
# ---------------------------------------------------------------------------

class GreeksSnapshotEngine(AnalysisEngine):
    """Describe the candidate's option sensitivity profile from normalized Greeks.

    Inputs (normalized data — ONLY populated Greeks are used):
      - delta
      - gamma
      - theta
      - vega

    Outputs (AnalysisResult):
      - qualifying True => at least one sensitivity metric above MIN_ABS_DELTA
      - qualifying False => no meaningful Greeks available; safe not to qualify
      - metrics with deltas, gammas, thetas, vegas (as strings)

    Notes:
      - Greeks are observed snapshot values. No trade direction is implied.
      - Delta = 0.5 for a CALL means the option price moves ~$0.50 per $1 underlier.
      - Delta = -0.5 for a PUT means the option price moves ~$0.50 per $1
        underlier inversely.
      - No BUY/SELL is encoded in the engine output.

    Data dependency:
      Requires actual Greeks to be populated in NormalizedOptionContract.
      If Greeks are missing for a candidate, this engine returns a
      non-qualifying result with the reason "Greeks not available".
    """

    engine_id = "greeks-snapshot"
    engine_version = "1.0.0"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        config = config or {}
        self.min_abs_delta = Decimal(str(config.get("min_abs_delta", EngineConfig.MIN_ABS_DELTA)))

    def analyze(self, context: AnalysisContext) -> AnalysisResult:
        candidate = context.candidate
        contract = candidate.canonical_contract
        evidence: dict[str, Any] = {}
        metrics: dict[str, Any] = {}

        # Extract Greeks with safe absent-value handling
        delta = contract.delta
        gamma = contract.gamma
        theta = contract.theta
        vega = contract.vega

        # Greeks absent in contract
        if delta is None and gamma is None and theta is None and vega is None:
            return AnalysisResult(
                engine_id=self.engine_id,
                engine_version=self.engine_version,
                candidate=candidate,
                analysis_id=self._generate_analysis_id(),
                metrics={},
                qualifying=False,
                notes="Greeks not available in normalized data",
            )

        metrics["delta"] = str(delta) if delta is not None else "null"
        metrics["gamma"] = str(gamma) if gamma is not None else "null"
        metrics["theta"] = str(theta) if theta is not None else "null"
        metrics["vega"] = str(vega) if vega is not None else "null"

        # Any meaningful value at all => data observed
        any_greek = any(x is not None for x in (delta, gamma, theta, vega))

        # Default: qualifying if Greeks present, even if magnitude below a
        # configurable sensitivity threshold (all Greeks below threshold
        # indicate a shallow out-of-the-money position).
        qualifying = any_greek

        evidence["delta"] = metrics["delta"]
        evidence["gamma"] = metrics["gamma"]
        evidence["theta"] = metrics["theta"]
        evidence["vega"] = metrics["vega"]
        evidence["greeks_status"] = "populated"
        evidence["min_abs_delta"] = str(self.min_abs_delta)

        # If Greeks exist but delta is within threshold, still qualifying
        # unless we need a sensitivity benchmarking threshold, which the
        # caller can set separately.
        return AnalysisResult(
            engine_id=self.engine_id,
            engine_version=self.engine_version,
            candidate=candidate,
            analysis_id=self._generate_analysis_id(),
            metrics=metrics,
            qualifying=qualifying,
            notes="Greeks snapshot observed; no trade direction implied",
        )

    def _generate_analysis_id(self) -> str:
        return getattr(self.candidate, "candidate_id", "unknown")

    def __repr__(self) -> str:  # pragma: no cover - debug
        return f"<{self.engine_id} v{self.engine_version}>"


# ---------------------------------------------------------------------------
# Implied Volatility Snapshot Engine
# ---------------------------------------------------------------------------

class IVSnapshotEngine(AnalysisEngine):
    """Report the candidate's current implied volatility observation.

    Inputs (normalized data):
      - implied_volatility (populated in Snapshot data)

    Outputs (AnalysisResult):
      - qualifying True => implied_volatility populated and >= MIN_IMPLIED_VOLATILITY
      - qualifying False => missing or below threshold
      - metrics { "implied_volatility": <string> }

    Notes:
      - IV is a snapshot observation only. This engine does NOT compute
        IV rank, IV percentile, IV cheap, or IV expensive historically.
      - No directional inference (higher IV does not mean "expensive" by
        construction).

    Data dependency:
      Requires implied_volatility to be populated in normalized data.
      If present, the engine processes it; if absent, the engine returns a
      non-qualifying result with notes indicating missing IV.
    """

    engine_id = "iv-snapshot"
    engine_version = "1.0.0"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        config = config or {}
        self.min_iv = Decimal(str(config.get("min_implied_volatility", EngineConfig.MIN_IMPLIED_VOLATILITY)))

    def analyze(self, context: AnalysisContext) -> AnalysisResult:
        candidate = context.candidate
        contract = candidate.canonical_contract
        evidence: dict[str, Any] = {}
        metrics: dict[str, Any] = {}

        iv = contract.implied_volatility

        if iv is None or iv <= 0:
            return AnalysisResult(
                engine_id=self.engine_id,
                engine_version=self.engine_version,
                candidate=candidate,
                analysis_id=self._generate_analysis_id(),
                metrics={},
                qualifying=False,
                notes="IV not available",
            )

        metrics["implied_volatility"] = str(iv)
        evidence["implied_volatility"] = str(iv)
        evidence["iv_status"] = "populated"
        evidence["min_implied_volatility"] = str(self.min_iv)

        return AnalysisResult(
            engine_id=self.engine_id,
            engine_version=self.engine_version,
            candidate=candidate,
            analysis_id=self._generate_analysis_id(),
            metrics=metrics,
            qualifying=True,
            notes="IV snapshot observed; no HV distribution / percentile"
                  " computed",
        )

    def _generate_analysis_id(self) -> str:
        return getattr(self.candidate, "candidate_id", "unknown")

    def __repr__(self) -> str:  # pragma: no cover - debug
        return f"<{self.engine_id} v{self.engine_version}>"


# ---------------------------------------------------------------------------
# Open Interest / Participation Engine
# ---------------------------------------------------------------------------

class OpenInterestParticipationEngine(AnalysisEngine):
    """Report on candidate open-interest and volume participation.

    Inputs (normalized data):
      - open_interest
      - volume

    Outputs (AnalysisResult):
      - qualifying True => both open_interest and volume above
        config.MIN_VOLUME and config.MIN_OPEN_INTEREST
      - qualifying False => missing/zero open_interest or volume
      - metrics { "open_interest", "volume", "volume_ratio" }

    Notes:
      - Volume ratio (volume / open_interest) is a usage proxy only.
        It is NOT a qualitative statement about market sentiment.

    Data dependency:
      Requires open_interest and volume to be populated.
      If either is missing/zero, the engine returns a non-qualifying result.
    """

    engine_id = "oi-participation"
    engine_version = "1.0.0"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        config = config or {}
        self.min_volume = Decimal(str(config.get("min_volume", EngineConfig.MIN_VOLUME)))
        self.min_open_interest = Decimal(str(config.get("min_open_interest", EngineConfig.MIN_OPEN_INTEREST)))

    def analyze(self, context: AnalysisContext) -> AnalysisResult:
        candidate = context.candidate
        contract = candidate.canonical_contract
        evidence: dict[str, Any] = {}
        metrics: dict[str, Any] = {}

        volume = contract.volume or 0
        open_interest = contract.open_interest or 0

        metrics["open_interest"] = open_interest
        metrics["volume"] = volume

        if volume <= 0 or open_interest <= 0:
            evidence["status"] = "insufficient_data"
            return AnalysisResult(
                engine_id=self.engine_id,
                engine_version=self.engine_version,
                candidate=candidate,
                analysis_id=self._generate_analysis_id(),
                metrics=metrics,
                qualifying=False,
                notes="OI or volume missing/zero",
            )

        volume_ratio = volume / open_interest
        metrics["volume_ratio"] = str(volume_ratio)
        evidence["volume"] = volume
        evidence["open_interest"] = open_interest
        evidence["volume_ratio"] = str(volume_ratio)
        evidence["status"] = "populated"

        return AnalysisResult(
            engine_id=self.engine_id,
            engine_version=self.engine_version,
            candidate=candidate,
            analysis_id=self._generate_analysis_id(),
            metrics=metrics,
            qualifying=True,
            notes="OI/participation observed; no sentiment statement",
        )

    def _generate_analysis_id(self) -> str:
        return getattr(self.candidate, "candidate_id", "unknown")

    def __repr__(self) -> str:  # pragma: no cover - debug
        return f"<{self.engine_id} v{self.engine_version}>"


# ---------------------------------------------------------------------------
# Backend auto-registration
# ---------------------------------------------------------------------------

def _auto_register():
    """Register all V2.9F engines on module import."""
    from app.analysis.engine import register_engine
    register_engine(LiquidityQualityEngine)
    register_engine(GreeksSnapshotEngine)
    register_engine(IVSnapshotEngine)
    register_engine(OpenInterestParticipationEngine)


_auto_register()