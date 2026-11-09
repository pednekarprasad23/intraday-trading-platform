"""Analysis Engine Interface / Foundation — V2.9E.

Provides the generic contract that analysis engines implement.
This is a foundation-only phase: defines types/contexts, does NOT implement
real analysis engines (those belong to V2.9F).

Strictly decoupled from execution, paper trading, and broker modules.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


@dataclass
class AnalysisContext:
    """Input context for an analysis engine.

    Received from a MarketCandidate and enriched with screening evidence.
    No execution, order, or recommendation logic.
    """

    candidate: "MarketCandidate"  # forward ref; actual type imported at use site
    spot_price: Decimal
    expiry: str | None = None
    strike: Decimal | None = None
    option_type: str | None = None
    evidence: dict[str, Any] | None = field(default_factory=dict)
    discovery_reason: str = ""
    config: dict[str, Any] | None = field(default_factory=dict)


class AnalysisResult:
    """Result produced by an analysis engine.

    Pure data container — no trading recommendations, no order instructions,
    no execution directives. All fields are observable facts or
    engine-internal metrics, presented transparently.
    """

    def __init__(
        self,
        engine_id: str,
        engine_version: str,
        candidate: "MarketCandidate",
        analysis_id: str,
        metrics: dict[str, Any] | None = None,
        qualifying: bool = False,
        notes: str | None = None,
    ):
        self.engine_id = engine_id
        self.engine_version = engine_version
        self.candidate = candidate
        self.analysis_id = analysis_id
        self.metrics = metrics or {}
        self.qualifying = qualifying
        self.notes = notes


class AnalysisEngine(ABC):
    """Abstract base contract for analysis engines.

    Subclasses must implement :meth:`analyze` and declare:
    - engine_id / engine_version (for registry/discovery)
    - The analysis they perform (pure screening/metrics, no strategy)
    - Input type (AnalysisContext)
    - Output type (AnalysisResult)

    Important: Implementations must maintain ZERO imports/dependencies into:
      PaperSignal, PaperOrder, PaperFill, PaperPosition,
      PaperExecutionService, broker adapters, execution engine,
      live execution, position sizing, risk/order routing.
    """

    @property
    @abstractmethod
    def engine_id(self) -> str:
        """Unique engine identifier (repository-consistent name)."""

    @property
    @abstractmethod
    def engine_version(self) -> str:
        """Engine version string."""

    @abstractmethod
    def analyze(self, context: AnalysisContext) -> AnalysisResult:
        """Perform analysis and return an AnalysisResult.

        Must be deterministic for same input.
        Must not produce side effects.
        Must not import execution / broker / paper modules.
        """


# Registry of named engines for discovery/bootstrap purposes.
# Populated by V2.9F engine registration; engines self-register at import.
ANALYSIS_ENGINES: dict[str, type[AnalysisEngine]] = {}

#: Required engine configuration keys (populated by bootstrap, read-only for engines).
ENGINE_CONFIG_SCHEMA: dict[str, type[Any]] = {}


def register_engine(engine_cls: type[AnalysisEngine]) -> None:
    """Register an analysis engine class in the global registry."""
    ANALYSIS_ENGINES[engine_cls.engine_id] = engine_cls


def unregister_engine(engine_id: str) -> None:
    """Remove an analysis engine from the registry."""
    ANALYSIS_ENGINES.pop(engine_id, None)


def get_engine(engine_id: str) -> type[AnalysisEngine] | None:
    """Look up an engine class by its registered ID."""
    return ANALYSIS_ENGINES.get(engine_id)


def list_engines() -> list[str]:
    """Return sorted list of registered engine IDs."""
    return sorted(ANALYSIS_ENGINES.keys())