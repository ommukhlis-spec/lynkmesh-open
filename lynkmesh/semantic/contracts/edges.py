"""Edge primitives — typed semantic edges."""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .confidence import ConfidenceClass
from .provenance import ProvenanceChain, SourceLocation
from .resolution import RejectReason


class EdgeType(Enum):
    """Closed vocabulary of semantic edges."""
    CALLS         = "calls"
    INSTANTIATES  = "instantiates"
    IMPLEMENTS    = "implements"
    EXTENDS       = "extends"
    USES          = "uses"
    RETURNS       = "returns"
    THROWS        = "throws"
    DISPATCHES    = "dispatches"
    ROUTES_TO     = "routes_to"
    READS         = "reads"
    WRITES        = "writes"
    CONTAINS      = "contains"


@dataclass(frozen=True)
class CallEdge:
    """
    Typed semantic edge with confidence + provenance metadata.

    NOT YET wired to graph builder in PR 1. This is forward-compat
    schema; EdgeBuilder migration happens in PR 2/PR 4.
    """
    source_id: str
    target_id: str
    edge_type: EdgeType
    confidence: ConfidenceClass
    site: SourceLocation
    provenance: ProvenanceChain = ProvenanceChain()
    # If set, this CallEdge represents a rejected resolution
    # (kept for telemetry, NOT inserted into graph).
    reject_reason: Optional[RejectReason] = None

    @property
    def is_emitted(self) -> bool:
        """True when this edge will be inserted into the graph."""
        return self.reject_reason is None