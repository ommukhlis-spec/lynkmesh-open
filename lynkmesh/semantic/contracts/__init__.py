"""
Semantic Contracts — cross-engine primitives for LynkMesh.

These types are PUBLIC API across resolver, architecture engine,
impact engine, and explain engine. Treat as semantic contracts,
not implementation details.

Stability: frozen dataclasses + closed enums. Any field addition
requires schema_version bump in debug_export.SCHEMA_VERSION.
"""

from .confidence import ConfidenceClass, ConfidenceReport
from .provenance import ProvenanceStep, ProvenanceChain, SourceLocation
from .resolution import (
    FailureReason,
    RejectReason,
    ResolutionResult,
    ResolutionOutcome,
)
from .edges import EdgeType, CallEdge
from .telemetry import ResolutionTelemetry, InvariantViolation
from .debug_export import (
    SCHEMA_VERSION,
    BuildMetadata,
    ResolutionDebugReport,
)

__all__ = [
    "ConfidenceClass",
    "ConfidenceReport",
    "ProvenanceStep",
    "ProvenanceChain",
    "SourceLocation",
    "FailureReason",
    "RejectReason",
    "ResolutionResult",
    "ResolutionOutcome",
    "EdgeType",
    "CallEdge",
    "ResolutionTelemetry",
    "InvariantViolation",
    "SCHEMA_VERSION",
    "BuildMetadata",
    "ResolutionDebugReport",
]