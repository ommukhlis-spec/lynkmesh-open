"""
Resolution primitives.

Semantic distinction enforced here:

  FailureReason  : symbol target NOT FOUND (resolution failed).
  RejectReason   : symbol target FOUND but edge NOT EMITTED.

These are not interchangeable.
"""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .confidence import ConfidenceClass
from .provenance import ProvenanceChain, SourceLocation


class FailureReason(Enum):
    """Closed enum. Every non-resolution MUST pick exactly one."""

    STATIC_METHOD_NOT_FOUND     = "static_method_not_found"
    NO_OBJECT                    = "no_object"

    KNOWN_FRAMEWORK_EXTERNAL     = "known_framework_external"

    # NEW
    BUILTIN_TYPE_SKIPPED         = "builtin_type_skipped"

    # NEW
    NO_RESOLUTION_STRATEGY       = "no_resolution_strategy"

    INHERITANCE_AMBIGUOUS        = "inheritance_ambiguous"
    INTERFACE_NO_IMPLEMENTER     = "interface_no_implementer"

    DYNAMIC_METHOD_NAME          = "dynamic_method_name"
    CHAINED_CALL_BROKEN          = "chained_call_broken"

    ASSIGNMENT_LOST              = "assignment_lost"
    RETURN_TYPE_UNKNOWN          = "return_type_unknown"

    ARRAY_ACCESS_UNRESOLVED      = "array_access_unresolved"

    UNKNOWN_REASON               = "unknown_reason"  # AUDIT-MARKED. Must remain rare.


class RejectReason(Enum):
    """Closed enum. Used when target found but edge not materialized."""
    DUPLICATE_EDGE        = "duplicate_edge"
    INVALID_TARGET        = "invalid_target"
    CONFIDENCE_FILTERED   = "confidence_filtered"
    SELF_LOOP_FILTERED    = "self_loop_filtered"
    NOT_YET_IMPLEMENTED   = "not_yet_implemented"  # transitional, removed by Sprint 2.7.B exit


class ResolutionOutcome(Enum):
    """
    Three-state outcome. Mutually exclusive.

      RESOLVED  : callee_id present, will become an edge.
      REJECTED  : callee_id present, but edge was filtered out.
      NO_TARGET : callee_id None, no symbol matched.
    """
    RESOLVED   = "resolved"
    REJECTED   = "rejected"
    NO_TARGET  = "no_target"


@dataclass(frozen=True)
class ResolutionResult:
    """
    Single resolution attempt result.

    Invariants (enforced in __post_init__):

      outcome == RESOLVED   ⇒ callee_id is not None
                              and failure_reason is None
                              and reject_reason is None
      outcome == REJECTED   ⇒ callee_id is not None
                              and failure_reason is None
                              and reject_reason is not None
      outcome == NO_TARGET  ⇒ callee_id is None
                              and failure_reason is not None
                              and reject_reason is None
    """
    caller_id: str
    site: SourceLocation
    confidence: ConfidenceClass
    outcome: ResolutionOutcome
    provenance: ProvenanceChain = ProvenanceChain()
    callee_id: Optional[str] = None
    failure_reason: Optional[FailureReason] = None
    reject_reason: Optional[RejectReason] = None

    def __post_init__(self):
        if self.outcome == ResolutionOutcome.RESOLVED:
            if self.callee_id is None:
                raise ValueError("RESOLVED requires callee_id")
            if self.failure_reason is not None:
                raise ValueError("RESOLVED must not carry failure_reason")
            if self.reject_reason is not None:
                raise ValueError("RESOLVED must not carry reject_reason")
        elif self.outcome == ResolutionOutcome.REJECTED:
            if self.callee_id is None:
                raise ValueError("REJECTED requires callee_id (target was found)")
            if self.failure_reason is not None:
                raise ValueError("REJECTED must not carry failure_reason")
            if self.reject_reason is None:
                raise ValueError("REJECTED requires reject_reason")
        elif self.outcome == ResolutionOutcome.NO_TARGET:
            if self.callee_id is not None:
                raise ValueError("NO_TARGET must not carry callee_id")
            if self.failure_reason is None:
                raise ValueError("NO_TARGET requires failure_reason")
            if self.reject_reason is not None:
                raise ValueError("NO_TARGET must not carry reject_reason")
        else:
            raise ValueError(f"unknown outcome: {self.outcome}")