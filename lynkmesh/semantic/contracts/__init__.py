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

from .mesh_context_report import (
    MESH_CONTEXT_SCHEMA_VERSION,
    MESH_CONTEXT_REPORT_TYPE,
    MeshProjectMetadata,
    MeshBuildMetadata,
    MeshProvenance,
    MeshContextReport,
    build_mesh_context_report,
    find_unsafe_report_strings,
)
from .mesh_context_diff import (
    MESH_CONTEXT_BENCHMARK_VECTOR_SCHEMA_VERSION,
    MESH_CONTEXT_DIFF_SCHEMA_VERSION,
    build_mesh_context_benchmark_vector,
    diff_mesh_context_benchmark_vectors,
    build_mesh_context_report_diff,
)

from .mesh_context_ai_pack import (
    MESH_CONTEXT_AI_PACK_PURPOSE,
    MESH_CONTEXT_AI_PACK_SCHEMA_VERSION,
    MESH_CONTEXT_AI_PACK_SOURCE_REPORT_SCHEMA_VERSION,
    MESH_CONTEXT_AI_PACK_TOKEN_ESTIMATOR,
    SUPPORTED_MESH_CONTEXT_AI_PACK_PROFILES,
    MeshContextAIContextPack,
    MeshContextAITaskGuide,
    MeshContextBudget,
    build_mesh_context_ai_pack,
    estimate_mesh_context_tokens,
    find_unsafe_ai_pack_strings,
)

from .mesh_context_token_benchmark import (
    MESH_CONTEXT_TOKEN_BENCHMARK_DIFF_SCHEMA_VERSION,
    MESH_CONTEXT_TOKEN_BENCHMARK_SCHEMA_VERSION,
    MeshContextTokenBenchmark,
    MeshContextTokenProfileBenchmark,
    build_mesh_context_token_benchmark,
    compare_mesh_context_token_benchmarks,
    find_unsafe_token_benchmark_strings,
)

from .mesh_context_structural_validation import (
    MESH_CONTEXT_STRUCTURAL_VALIDATION_SCHEMA_VERSION,
    MeshContextStructuralCheck,
    MeshContextStructuralValidation,
    build_mesh_context_structural_validation,
    find_unsafe_structural_validation_strings,
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
    "MESH_CONTEXT_SCHEMA_VERSION",
    "MESH_CONTEXT_REPORT_TYPE",
    "MeshProjectMetadata",
    "MeshBuildMetadata",
    "MeshProvenance",
    "MeshContextReport",
    "build_mesh_context_report",
    "find_unsafe_report_strings",
    "MESH_CONTEXT_BENCHMARK_VECTOR_SCHEMA_VERSION",
    "MESH_CONTEXT_DIFF_SCHEMA_VERSION",
    "build_mesh_context_benchmark_vector",
    "diff_mesh_context_benchmark_vectors",
    "build_mesh_context_report_diff",
    "build_mesh_context_benchmark_vector",
    "diff_mesh_context_benchmark_vectors",
    "build_mesh_context_report_diff",    "MESH_CONTEXT_TOKEN_BENCHMARK_DIFF_SCHEMA_VERSION",
    "MESH_CONTEXT_TOKEN_BENCHMARK_SCHEMA_VERSION",
    "MeshContextTokenBenchmark",
    "MeshContextTokenProfileBenchmark",
    "build_mesh_context_token_benchmark",
    "compare_mesh_context_token_benchmarks",
    "find_unsafe_token_benchmark_strings",
    "MESH_CONTEXT_STRUCTURAL_VALIDATION_SCHEMA_VERSION",
    "MeshContextStructuralCheck",
    "MeshContextStructuralValidation",
    "build_mesh_context_structural_validation",
    "find_unsafe_structural_validation_strings",

]