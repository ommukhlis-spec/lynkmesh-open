"""Confidence primitives — first-class semantic property."""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Mapping


class ConfidenceClass(Enum):
    """
    Closed enum. Every resolution and edge MUST carry exactly one.
    Order is significant: descending trustworthiness.
    """
    EXACT = "exact"
    PROPAGATED = "propagated"
    HEURISTIC = "heuristic"
    FRAMEWORK = "framework"
    EXTERNAL = "external"
    UNKNOWN = "unknown"

    @property
    def trust_rank(self) -> int:
        """Lower number = more trusted. For deterministic ordering."""
        return _TRUST_RANK[self]


_TRUST_RANK: Mapping[ConfidenceClass, int] = MappingProxyType({
    ConfidenceClass.EXACT:      0,
    ConfidenceClass.PROPAGATED: 1,
    ConfidenceClass.FRAMEWORK:  2,
    ConfidenceClass.HEURISTIC:  3,
    ConfidenceClass.EXTERNAL:   4,
    ConfidenceClass.UNKNOWN:    5,
})


@dataclass(frozen=True)
class ConfidenceReport:
    """
    Confidence with explainable factor breakdown.

    Bare floats are forbidden in cross-engine reports. Every
    confidence_score MUST come with the factors that produced it.

    Multiplicative model: score = product of factors.
    Caller is responsible for ensuring multiplicative consistency
    (or computing score via from_factors()).
    """
    score: float
    factors: Mapping[str, float]

    def __post_init__(self):
        if not (0.0 <= self.score <= 1.0):
            raise ValueError(
                f"ConfidenceReport.score must be in [0,1], got {self.score}"
            )
        if not self.factors:
            raise ValueError("ConfidenceReport.factors must not be empty")
        for name, val in self.factors.items():
            if not (0.0 <= val <= 1.0):
                raise ValueError(
                    f"factor {name!r} out of range [0,1]: {val}"
                )
        # Freeze the mapping to prevent post-hoc mutation.
        object.__setattr__(self, "factors", MappingProxyType(dict(self.factors)))

    @classmethod
    def from_factors(cls, factors: Mapping[str, float]) -> "ConfidenceReport":
        """Multiplicative composition. Empty factors disallowed."""
        if not factors:
            raise ValueError("from_factors requires at least one factor")
        score = 1.0
        for v in factors.values():
            score *= v
        return cls(score=score, factors=factors)