"""Provenance — explainability primitive."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class SourceLocation:
    """File, line, col of a syntactic event (call site, definition, etc)."""
    file: str
    line: int
    col: int

    def __post_init__(self):
        if self.line < 0 or self.col < 0:
            raise ValueError(
                f"SourceLocation line/col must be non-negative, "
                f"got line={self.line} col={self.col}"
            )


@dataclass(frozen=True)
class ProvenanceStep:
    """
    Single resolution step. `kind` is a closed vocabulary
    enforced at the resolver layer, not here, to allow extension
    without contract bump.

    Examples of kind:
      - "constructor_injection"
      - "assignment_propagation"
      - "type_registry_lookup"
      - "inheritance_match"
      - "interface_match"
      - "framework_fallback"
      - "heuristic_fallback"
    """
    kind: str
    detail: str


@dataclass(frozen=True)
class ProvenanceChain:
    """
    Ordered trail of resolution steps from call site to resolved target.
    Empty chain is valid for failures (no resolution happened).
    """
    steps: Tuple[ProvenanceStep, ...] = ()

    def append(self, step: ProvenanceStep) -> "ProvenanceChain":
        """Returns a new chain. Original is immutable."""
        return ProvenanceChain(steps=self.steps + (step,))

    def __len__(self) -> int:
        return len(self.steps)