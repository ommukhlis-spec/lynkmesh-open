# lynkmesh/core/graph_version.py
"""
Stage 3.0.0 — Graph Versioning Infrastructure

Implements GraphVersion as a foundational deterministic identity primitive,
per Stage 3 Architecture Specification §20.

This module provides:
    - VersionMetadata: per-run identity (no content hash)
    - GraphVersion: full version (metadata + content fingerprint)
    - compute_node_identity / compute_edge_identity: semantic identity from
      verified runtime schema, excluding per-build UUIDs
    - compute_content_hash: deterministic SHA-256 over canonicalized graph state
    - verify_pipeline_determinism: PYTHONHASHSEED enforcement
    - is_same_graph / is_same_content / is_serialization_compatible: explicit
      compatibility predicates (replacing the conflated is_compatible_with)

Tier: 0 (core).
Allowed dependencies: stdlib only (uuid, datetime, hashlib, json, os, dataclasses, typing).
Forbidden: imports from graph/, query/, analysis/, exporters/, ai/, pipeline/,
           or even from lynkmesh.core.graph_core (which would be circular).

Determinism guarantees:
    - With PYTHONHASHSEED=0, content_hash is byte-identical across runs.
    - All collections sorted before serialization (no set iteration leaks).
    - All floats normalized via format(value, '.17g') (cross-platform stable
      for IEEE 754 round-trip).
    - All JSON serialization uses pinned options
      (sort_keys=True, separators=(',',':'), ensure_ascii=True).
    - All UUIDs (node.id, edge.id) excluded from hash; semantic identity used
      instead, defeating the per-build randomness that would otherwise produce
      a fresh content_hash on every run.

Invariants enforced (cross-referenced by I-number to contract v2 §6):
    I1  — content determinism within process
    I2  — cross-run determinism (with PYTHONHASHSEED=0)
    I3  — sensitivity (different graphs → different hashes)
    I4  — order independence (canonicalization)
    I5  — hash format (64-char lowercase hex)
    I6  — node identity excludes UUID
    I7  — edge identity excludes UUID
    I8  — cross-build identity stability
    I11 — stable graph_id from project path
    I12 — unique build_id per call
    I14 — pipeline_seed consistency
    I16 — equality reflexivity
    I17 — equality requires all fields
    I18 — hashable equality
    I19 — predicate ordering
    I20 — cache predicate semantics
    I22 — atomic transitions (frozen dataclass)
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple


# =============================================================================
# Module-level constants (contract v2 §5.10)
# =============================================================================

SCHEMA_VERSION: str = "3.0.0"
HASH_ALGORITHM: str = "sha256"
EXPECTED_PIPELINE_SEED: str = "0"

# Pinned JSON serialization options. Defaults could shift across CPython
# versions; pinning eliminates that risk. (Audit #1.2, R1.)
JSON_SERIALIZATION_OPTIONS: Dict[str, Any] = {
    "sort_keys": True,
    "separators": (",", ":"),
    "ensure_ascii": True,
}

# Hash payload structure constants. Namespace literals prevent collision
# between identical content under different roles. The null byte separator
# is unambiguous: it cannot appear in canonical JSON output (which is ASCII).
HASH_NODES_PREFIX: bytes = b"NODES:"
HASH_EDGES_PREFIX: bytes = b"|EDGES:"
HASH_BLOB_SEPARATOR: bytes = b"\x00"

# Stable namespace UUID for graph_id derivation. UUID5(NAMESPACE, project_path)
# produces identical graph_id across runs of the same project. Generated once
# offline; never regenerate or this breaks all graph_id stability.
_LYNKMESH_GRAPH_ID_NAMESPACE: uuid.UUID = uuid.UUID(
    "6c7e9a3b-1f4d-5b2e-8a3c-7d9e1f2b3c4d"
)


# =============================================================================
# Hash field allowlists (Phase B Adaptation 4 + 5)
#
# These define EXACTLY which fields participate in semantic identity. Adding
# a new field requires schema_version bump (per contract §11.2). Subtracting
# a field also requires bump. The allowlist is exhaustive — any node/edge
# field not in this list is excluded from hash, by design.
# =============================================================================

# Node-level fields that are hash-relevant (top-level keys of a node dict).
# `id` is excluded (per-build UUID). `file` is excluded (alias of file_path).
# `extra` is included but recursively filtered by _NODE_EXTRA_HASH_FIELDS.
_NODE_HASH_FIELDS: Tuple[str, ...] = (
    "qualified_name",
    "type",
    "file_path",
    "layer",
    "name",
)

# Within node["extra"], only these keys participate in hash. Anything else
# in `extra` is treated as transient/derived (computed values, IR-derived
# orderings, importance scores, etc.). See Phase B Adaptation 4 for the
# full include/exclude table.
_NODE_EXTRA_HASH_FIELDS: frozenset = frozenset({
    "class",          # method's owning class fqn
    "extends",        # class inheritance
    "interfaces",     # class implementations
    "traits",         # class traits
    "return_type",    # method return type
    "visibility",     # method visibility
    "params",         # method parameters
    "properties",     # class properties
    "entry",          # entry-point flag
    "entry_type",     # entry-point classification
    "target_class",   # external nodes only
    "method",         # external nodes only
})

# Edge-level top-level fields that are hash-relevant. `id` is excluded
# (per-build UUID). `from`/`to` are NOT hashed directly; they are
# dereferenced to source/target node identity via the graph.nodes mapping.
_EDGE_HASH_TOP_FIELDS: Tuple[str, ...] = (
    "type",
    "semantic",
)

# Edge metadata sub-fields that are hash-relevant. `raw_call` is excluded
# (transient deep-copy of IR call dict). `call_type` is excluded (derived
# from raw_call). Only `line` survives as identity-relevant source location.
_EDGE_METADATA_HASH_FIELDS: frozenset = frozenset({
    "line",
})


# =============================================================================
# Error types (contract v2 §5.11)
# =============================================================================

class IncompatibleSchemaError(Exception):
    """Raised when from_dict receives data from a schema_version that
    cannot be loaded by current code (e.g., future major version)."""


class MalformedVersionError(Exception):
    """Raised when from_dict receives malformed input (missing required
    fields, wrong types, etc.)."""


# =============================================================================
# Pipeline determinism enforcement (contract v2 §5.9, §8.5)
# =============================================================================

def verify_pipeline_determinism() -> None:
    """
    Verify that PYTHONHASHSEED is set to "0".

    Per spec §15.2, deterministic graph identity requires fixed hash seed.
    Default Python hash randomization would cause set/dict iteration order
    to vary across runs, which (although already mitigated by our
    canonicalization) would also affect any third-party library code paths
    in the pipeline.

    Called once from pipeline/orchestrator.py:Orchestrator.__init__.
    Per contract §2.5, NOT called from GraphCore (which is environment-
    agnostic storage).

    Raises:
        EnvironmentError: if PYTHONHASHSEED is not "0".
    """
    actual = os.environ.get("PYTHONHASHSEED")
    if actual != EXPECTED_PIPELINE_SEED:
        raise EnvironmentError(
            f"PYTHONHASHSEED must be {EXPECTED_PIPELINE_SEED!r} for "
            f"deterministic LynkMesh pipeline; got {actual!r}. "
            f"Set PYTHONHASHSEED=0 in environment before running."
        )


# =============================================================================
# Identity computation
# =============================================================================

def _canonicalize_value(value: Any) -> Any:
    """
    Recursively transform a value into a canonically-orderable representation
    suitable for deterministic JSON serialization.

    Rules (contract v2 §8.2):
        - dict → keys sorted lexicographically, values recursively canonicalized
        - list → preserved in original order (producer's responsibility for
          deterministic ordering); contents recursively canonicalized
        - tuple → converted to list, contents recursively canonicalized
        - set / frozenset → converted to sorted list (canonical ordering)
        - float → string via format(v, '.17g') for IEEE 754 round-trip
          deterministic across CPython versions and platforms (audit #1.1, R1)
        - bool, int, str, None → passed through (JSON-serializable as-is)

    Note: lists are NOT sorted. Producer (parser, builder, resolver) must
    emit lists in deterministic order. Sorting lists would silently rewrite
    user intent (e.g., method parameter order matters semantically).

    Note: floats are converted to strings — they will be JSON-serialized as
    quoted strings. This is intentional. JSON's default float serialization
    is platform-dependent for non-exact-representable values; string
    representation via .17g is fully deterministic.
    """
    if isinstance(value, dict):
        # Recursive canonicalization with sorted keys. Note: even though
        # JSON_SERIALIZATION_OPTIONS includes sort_keys=True (which sorts
        # the OUTPUT json's top-level keys), we still need this recursive
        # pass to handle floats embedded in nested dicts and to convert
        # any sets at any depth. (Audit #1.3.)
        return {k: _canonicalize_value(value[k]) for k in sorted(value.keys())}
    if isinstance(value, (list, tuple)):
        return [_canonicalize_value(v) for v in value]
    if isinstance(value, (set, frozenset)):
        # Sets have no inherent order. Convert to sorted list for determinism.
        # We sort by the canonical form to handle non-string set elements.
        canonicalized = [_canonicalize_value(v) for v in value]
        # json.dumps each for sortability; this is correct because all
        # canonicalized values are JSON-serializable scalars or containers.
        return sorted(
            canonicalized,
            key=lambda x: json.dumps(x, **JSON_SERIALIZATION_OPTIONS),
        )
    if isinstance(value, float):
        # Float normalization: .17g preserves IEEE 754 round-trip precision
        # and is platform-deterministic. (Contract §8.3, audit #1.1.)
        # Result is a string; JSON will serialize as quoted string.
        return format(value, ".17g")
    # bool, int, str, None: JSON-native, no transformation needed.
    return value


def _canonical_json(obj: Any) -> str:
    """
    Serialize a (canonicalized) object to canonical JSON string.

    Pre-condition: obj has been passed through _canonicalize_value, so it
    contains no sets, no floats (all converted to .17g strings), no tuples.

    Contract: pinned options per JSON_SERIALIZATION_OPTIONS.
    Future-proof: defaults could change in CPython; this never relies on them.
    """
    return json.dumps(obj, **JSON_SERIALIZATION_OPTIONS)


def _normalize_file_path(file_path: Optional[str]) -> Optional[str]:
    """
    Normalize a file path for hash inclusion.

    Per contract §8.8, paths must be normalized to forward slashes for
    cross-platform stability. Building on Windows produces backslashes;
    building on Linux produces forward slashes; the same logical project
    must produce identical hashes regardless.

    None is preserved as None (external nodes have no file path; this is
    a valid identity component, not "missing data").
    """
    if file_path is None:
        return None
    # Replace backslashes with forward slashes. This handles Windows paths.
    # Already-normalized paths are unaffected.
    return file_path.replace("\\", "/")


def compute_node_identity(node: Mapping[str, Any]) -> Dict[str, Any]:
    """
    Compute the hash-relevant identity of a graph node.

    Per Phase B Adaptation, this excludes node["id"] (per-build UUID),
    node["file"] (alias of file_path), and any extra-dict keys not in
    _NODE_EXTRA_HASH_FIELDS.

    The result is a canonicalized dict suitable for inclusion in a
    deterministic hash. Same node (semantically) → same identity, regardless
    of UUID assignment.

    Args:
        node: A node dict from GraphCore.nodes.values().

    Returns:
        Canonicalized identity dict. None values are preserved (e.g., for
        external nodes with no file_path).

    Invariant I6: the returned dict is independent of node["id"].
    """
    identity: Dict[str, Any] = {}

    # Top-level fields from allowlist.
    for key in _NODE_HASH_FIELDS:
        value = node.get(key)
        if key == "file_path":
            value = _normalize_file_path(value)
        identity[key] = value

    # extra dict: filtered by allowlist, then recursively canonicalized.
    # We extract the allowlist keys first, then canonicalize, so transient
    # keys never enter the canonicalization stream (cleaner audit trail).
    raw_extra = node.get("extra")
    if isinstance(raw_extra, dict):
        filtered_extra = {
            k: raw_extra[k]
            for k in raw_extra
            if k in _NODE_EXTRA_HASH_FIELDS
        }
    else:
        # Defensive: extra should always be a dict per add_node contract,
        # but if it's missing or wrong type, treat as empty.
        filtered_extra = {}
    identity["extra"] = _canonicalize_value(filtered_extra)

    # Canonicalize the top-level fields too (handles any nested float/set).
    return _canonicalize_value(identity)


def compute_edge_identity(
    edge: Mapping[str, Any],
    nodes: Mapping[str, Mapping[str, Any]],
) -> Dict[str, Any]:
    """
    Compute the hash-relevant identity of a graph edge.

    Per Phase B Adaptation, this dereferences edge["from"]/edge["to"]
    (which are per-build UUIDs) into their corresponding node identities.
    Also excludes edge["id"], metadata.raw_call, metadata.call_type.

    Edge identity is therefore independent of the per-build UUID assignment
    of source/target nodes — moving a method between files would change
    file_path and thus identity (correct), but rebuilding the same graph
    twice produces identical edge identity (correct).

    Args:
        edge: An edge dict from GraphCore.edges.
        nodes: The graph.nodes mapping for source/target lookup.

    Returns:
        Canonicalized identity dict.

    Invariant I7: independent of edge["id"], edge["from"] UUID, edge["to"] UUID
    (only the dereferenced node identity matters).

    Note on missing source/target: if either node is not in the nodes mapping
    (which would indicate graph corruption), the identity field is None.
    This is a defensive fallback and would surface as a hash sensitivity
    test failure — by design.
    """
    identity: Dict[str, Any] = {}

    # Dereference source and target via the nodes mapping. The "from"/"to"
    # fields contain per-build UUIDs which we DO NOT hash; we hash the
    # node identities they point to.
    source_node = nodes.get(edge.get("from"))
    target_node = nodes.get(edge.get("to"))
    identity["source_identity"] = (
        compute_node_identity(source_node) if source_node is not None else None
    )
    identity["target_identity"] = (
        compute_node_identity(target_node) if target_node is not None else None
    )

    # Top-level allowlisted edge fields.
    for key in _EDGE_HASH_TOP_FIELDS:
        identity[key] = edge.get(key)

    # Confidence: float-normalized via .17g. Always present (add_edge
    # casts to float). We use a distinct key suffix `_str` to make it
    # explicit that this is the canonical string form.
    confidence = edge.get("confidence")
    if confidence is not None:
        # Defensive: confidence should be float per add_edge, but coerce
        # for safety. Non-numeric input would raise here, which is correct.
        identity["confidence_str"] = format(float(confidence), ".17g")
    else:
        identity["confidence_str"] = None

    # Optional fields. Per Phase B Adaptation 6, flow_id and weight are
    # included if present (semantically meaningful for AI tracing).
    flow_id = edge.get("flow_id")
    if flow_id is not None:
        identity["flow_id"] = flow_id
    weight = edge.get("weight")
    if weight is not None:
        identity["weight_str"] = format(float(weight), ".17g")

    # Metadata: filtered allowlist. Only `line` is identity-relevant.
    # `raw_call` and `call_type` are excluded as transient.
    raw_metadata = edge.get("metadata")
    if isinstance(raw_metadata, dict):
        filtered_metadata = {
            k: raw_metadata[k]
            for k in raw_metadata
            if k in _EDGE_METADATA_HASH_FIELDS
        }
    else:
        filtered_metadata = {}
    identity["metadata"] = _canonicalize_value(filtered_metadata)

    return _canonicalize_value(identity)


# =============================================================================
# Content hash computation (contract v2 §5.6, §8.1, §8.6, §8.7)
# =============================================================================

def compute_content_hash(
    nodes: Iterable[Mapping[str, Any]],
    edges: Iterable[Mapping[str, Any]],
) -> str:
    """
    Compute a deterministic SHA-256 fingerprint of graph content state.

    Algorithm (per contract §8):
        1. For each node, compute compute_node_identity(node) and serialize
           via canonical JSON.
        2. Sort node identity strings lexicographically (order independence).
        3. Concatenate with null-byte separator → nodes_blob.
        4. Build a node_id → node mapping for edge dereferencing.
        5. For each edge, compute compute_edge_identity(edge, nodes_map)
           and serialize via canonical JSON.
        6. Sort edge identity strings lexicographically.
        7. Concatenate with null-byte separator → edges_blob.
        8. payload = HASH_NODES_PREFIX + nodes_blob + HASH_EDGES_PREFIX +
                     edges_blob
        9. Return SHA-256 hexdigest of payload.

    The namespace prefixes prevent collision: a graph with one node "X" and
    no edges, vs a graph with no nodes and one "X-shaped" edge, would have
    structurally different payload bytes even though the inner blob bytes
    might somehow match (impossible in practice, but the prefix makes the
    impossibility structural rather than circumstantial).

    Args:
        nodes: Iterable of node dicts.
        edges: Iterable of edge dicts.

    Returns:
        64-character lowercase hex string (SHA-256).

    Invariant I1: byte-identical output for byte-identical input.
    Invariant I2: byte-identical output across runs (with PYTHONHASHSEED=0)
                  for the same logical graph state.
    Invariant I3: any change to a hash-relevant field changes the output.
    Invariant I4: presentation order independence.
    Invariant I5: output is exactly 64 lowercase hex chars.
    """
    # Materialize nodes once (we need to iterate twice: once for identity
    # computation, once for the dereferencing map).
    nodes_list: List[Mapping[str, Any]] = list(nodes)

    # Build node lookup map keyed by node["id"] for edge dereferencing.
    # This is the ONLY place we use node["id"] — and we use it only as
    # an internal lookup key, never as part of any hashed value.
    nodes_map: Dict[Any, Mapping[str, Any]] = {
        n.get("id"): n for n in nodes_list if n.get("id") is not None
    }

    # Compute node identities and serialize. Sort the resulting strings.
    # Sorting after serialization is correct: two semantically-identical
    # nodes produce identical canonical JSON, so they sort to adjacent
    # positions deterministically.
    node_identity_strings = sorted(
        _canonical_json(compute_node_identity(node))
        for node in nodes_list
    )
    nodes_blob = HASH_BLOB_SEPARATOR.join(
        s.encode("utf-8") for s in node_identity_strings
    )

    # Compute edge identities (with node dereferencing) and serialize.
    edge_identity_strings = sorted(
        _canonical_json(compute_edge_identity(edge, nodes_map))
        for edge in edges
    )
    edges_blob = HASH_BLOB_SEPARATOR.join(
        s.encode("utf-8") for s in edge_identity_strings
    )

    # Assemble payload with namespace prefixes.
    payload = HASH_NODES_PREFIX + nodes_blob + HASH_EDGES_PREFIX + edges_blob

    # SHA-256 (HASH_ALGORITHM constant). Using hashlib.new() rather than
    # hashlib.sha256() directly to honor the constant — if HASH_ALGORITHM
    # ever changes (with schema_version bump), only this line and the
    # constant need to change.
    digest = hashlib.new(HASH_ALGORITHM, payload).hexdigest()

    # Defensive invariant check: SHA-256 hexdigest is always 64 chars,
    # always lowercase. This assertion catches algorithm misconfiguration.
    assert len(digest) == 64, f"unexpected hash length: {len(digest)}"
    assert digest == digest.lower(), "hash digest must be lowercase"

    return digest


# =============================================================================
# graph_id and build_id generation
# =============================================================================

def compute_graph_id(
    project_path: str,
    override: Optional[str] = None,
) -> str:
    """
    Compute a stable graph_id for a project.

    Per contract §11.3, this supports an override path for sophisticated
    users (CI environments where checkout paths vary). When override is
    provided, it is returned verbatim. When override is None, graph_id is
    computed as UUID5(_LYNKMESH_GRAPH_ID_NAMESPACE, normalized_path).

    The path normalization (forward slashes, no trailing slash, lowercase
    on Windows-style drive letters) ensures the same project at logically
    the same location yields the same graph_id even if the path string
    representation varies slightly.

    Invariant I11: same project_path → same graph_id, deterministically.
    """
    if override is not None:
        return override
    # Normalize path: forward slashes, strip trailing separator.
    normalized = project_path.replace("\\", "/").rstrip("/")
    return str(uuid.uuid5(_LYNKMESH_GRAPH_ID_NAMESPACE, normalized))


def generate_build_id() -> str:
    """
    Generate a fresh build_id for a pipeline run.

    Always UUID4 (random). Each call produces a distinct value.

    Invariant I12: returned values are unique across calls.
    """
    return str(uuid.uuid4())


def _current_build_timestamp() -> str:
    """
    Return current UTC time in ISO-8601 format with microsecond precision.

    Used for VersionMetadata.build_timestamp. This is the ONLY place in
    this module that reads system time; per contract §7.4, this is the
    only sanctioned use of time.time-equivalent calls.
    """
    return datetime.now(timezone.utc).isoformat()


# =============================================================================
# VersionMetadata dataclass (contract v2 §5.1)
# =============================================================================

@dataclass(frozen=True)
class VersionMetadata:
    """
    Per-run identification metadata. Excludes content_hash.

    Used during pipeline mutation phases when content is not yet finalized.
    Once content_hash is computed, this is composed into a full GraphVersion.

    All fields immutable. Frozen dataclass enforces this at runtime.

    Per spec §15: no field derives from random state, id(), or memory
    addresses. Each field is either a stable identifier (graph_id from
    project path), a generated UUID4 (build_id), a timestamp (build_timestamp),
    or a constant (schema_version, pipeline_seed).
    """
    graph_id: str
    build_id: str
    build_timestamp: str
    git_commit: Optional[str]
    schema_version: str
    pipeline_seed: str

    @classmethod
    def create(
        cls,
        project_path: str,
        git_commit: Optional[str] = None,
        graph_id_override: Optional[str] = None,
    ) -> "VersionMetadata":
        """
        Factory for fresh metadata at the start of a pipeline run.

        Reads PYTHONHASHSEED at call time (not at import time) to capture
        the actual environment state during this build.
        """
        return cls(
            graph_id=compute_graph_id(project_path, graph_id_override),
            build_id=generate_build_id(),
            build_timestamp=_current_build_timestamp(),
            git_commit=git_commit,
            schema_version=SCHEMA_VERSION,
            pipeline_seed=os.environ.get("PYTHONHASHSEED", ""),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to plain dict for persistence (Stage 3.4) or logging."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "VersionMetadata":
        """
        Reconstruct from dict, validating required fields.

        Raises:
            MalformedVersionError: if required fields missing or wrong type.
        """
        required = (
            "graph_id", "build_id", "build_timestamp",
            "schema_version", "pipeline_seed",
        )
        for key in required:
            if key not in data:
                raise MalformedVersionError(
                    f"VersionMetadata.from_dict: missing required field {key!r}"
                )
        # git_commit is Optional but must be str or None.
        git_commit = data.get("git_commit")
        if git_commit is not None and not isinstance(git_commit, str):
            raise MalformedVersionError(
                f"VersionMetadata.from_dict: git_commit must be str or None, "
                f"got {type(git_commit).__name__}"
            )
        return cls(
            graph_id=str(data["graph_id"]),
            build_id=str(data["build_id"]),
            build_timestamp=str(data["build_timestamp"]),
            git_commit=git_commit,
            schema_version=str(data["schema_version"]),
            pipeline_seed=str(data["pipeline_seed"]),
        )


# =============================================================================
# GraphVersion dataclass (contract v2 §5.2)
# =============================================================================

@dataclass(frozen=True)
class GraphVersion:
    """
    Full graph version: per-run metadata + content fingerprint.

    Returned by GraphCore.version property.

    Per contract v2 §5.4 (audit #4.3), __hash__ is overridden to be
    deterministic across processes — based on content_hash (which is itself
    deterministic across runs with PYTHONHASHSEED=0). This enables
    GraphVersion to be used as a dict key with stable hashing in Stage 3.4
    persistence layer.

    Per contract v2 §5.3 (audit #4.1), this class exposes THREE distinct
    compatibility predicates:
        - is_same_graph: logical identity (same project)
        - is_same_content: cache equivalence (same fingerprint)
        - is_serialization_compatible: deserialization safety
    The conflated `is_compatible_with` from v1 is intentionally absent.
    """
    metadata: VersionMetadata
    content_hash: str

    # ---- Compatibility predicates (contract v2 §5.3) ---------------------

    def is_same_graph(self, other: "GraphVersion") -> bool:
        """
        Return True iff `other` describes the same logical project.

        Use case: identifying that two builds (different times, different
        machines, different commits) describe the same project.

        Implements I19: equality implies is_same_graph; reverse not required.
        """
        return self.metadata.graph_id == other.metadata.graph_id

    def is_same_content(self, other: "GraphVersion") -> bool:
        """
        Return True iff `other` has identical content fingerprint.

        Use case: cache lookups. If two GraphVersions have the same
        content_hash, any cached computation derived from one is valid
        for the other (per I20).

        This is the predicate cache layers MUST use.
        """
        return self.content_hash == other.content_hash

    def is_serialization_compatible(self, other: "GraphVersion") -> bool:
        """
        Return True iff `other` is loadable by code that produced `self`
        (or vice versa).

        Compatibility requires same schema_version (no breaking schema
        changes between them) AND same pipeline_seed (deterministic hash
        invariants are seed-bound).

        Use case: persistence load — verifying a serialized version can
        be deserialized safely by current code.
        """
        return (
            self.metadata.schema_version == other.metadata.schema_version
            and self.metadata.pipeline_seed == other.metadata.pipeline_seed
        )

    # ---- Equality and hashability (contract v2 §5.4) --------------------

    def __eq__(self, other: object) -> bool:
        """
        Logical identity equality: all fields match.

        Implements I17. Two GraphVersions differing in any field
        (including build_id, build_timestamp) are NOT equal.

        For caching semantics (which should ignore build_id/timestamp),
        callers MUST use is_same_content() instead of ==.
        """
        if not isinstance(other, GraphVersion):
            return NotImplemented
        return (
            self.metadata == other.metadata
            and self.content_hash == other.content_hash
        )

    def __hash__(self) -> int:
        """
        Process-stable hash derived from content_hash.

        Standard Python hash on tuples would use str.__hash__ which is
        affected by PYTHONHASHSEED. We've enforced PYTHONHASHSEED=0 in
        production, but for dict-key stability across processes (e.g.,
        Stage 3.4 persistence reload), we use the content_hash hex
        prefix as a deterministic int.

        Implements I18: equality implies hash equality (since equal
        GraphVersions have equal content_hash, they yield equal hash).
        """
        # Use first 16 hex chars (64 bits) of content_hash as the hash.
        # This is deterministic across runs and processes, and uses well
        # under Python's int range. (Audit #4.3.)
        return int(self.content_hash[:16], 16)

    def __repr__(self) -> str:
        """Human-readable summary; suitable for logging."""
        return (
            f"GraphVersion("
            f"graph_id={self.metadata.graph_id!s}, "
            f"build_id={self.metadata.build_id!s}, "
            f"content_hash={self.content_hash[:12]}..., "
            f"schema={self.metadata.schema_version}"
            f")"
        )

    # ---- Serialization (contract v2 §5.5) -------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize to plain dict for persistence (Stage 3.4) or logging.

        Round-trips losslessly through from_dict.
        """
        return {
            "metadata": self.metadata.to_dict(),
            "content_hash": self.content_hash,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "GraphVersion":
        """
        Reconstruct from dict, with explicit migration semantics.

        Per contract §5.11:
            - Raises IncompatibleSchemaError if schema_version is from a
              future major version (current code cannot understand it).
            - Raises MalformedVersionError if required fields missing or
              wrong type.

        Same-major-version data is loaded as-is. Past-major-version data
        is also loaded for now (no migrations exist yet); future stages
        may add migration logic via this entry point.
        """
        if not isinstance(data, Mapping):
            raise MalformedVersionError(
                f"GraphVersion.from_dict: expected mapping, got "
                f"{type(data).__name__}"
            )

        if "metadata" not in data:
            raise MalformedVersionError(
                "GraphVersion.from_dict: missing 'metadata' field"
            )
        if "content_hash" not in data:
            raise MalformedVersionError(
                "GraphVersion.from_dict: missing 'content_hash' field"
            )

        # Schema compatibility check: parse the schema_version from the
        # incoming metadata and reject if its major version exceeds ours.
        incoming_metadata = data["metadata"]
        if not isinstance(incoming_metadata, Mapping):
            raise MalformedVersionError(
                "GraphVersion.from_dict: 'metadata' must be a mapping"
            )
        incoming_schema = incoming_metadata.get("schema_version")
        if not isinstance(incoming_schema, str):
            raise MalformedVersionError(
                "GraphVersion.from_dict: schema_version must be a string"
            )
        # Major version comparison. Schema versions are dotted: "MAJOR.MINOR.PATCH".
        # Reject if incoming major > current major.
        try:
            incoming_major = int(incoming_schema.split(".", 1)[0])
            current_major = int(SCHEMA_VERSION.split(".", 1)[0])
        except (ValueError, IndexError):
            raise MalformedVersionError(
                f"GraphVersion.from_dict: malformed schema_version "
                f"{incoming_schema!r}"
            )
        if incoming_major > current_major:
            raise IncompatibleSchemaError(
                f"GraphVersion.from_dict: incoming schema_version "
                f"{incoming_schema!r} is from a future major version; "
                f"current code understands up to {SCHEMA_VERSION!r}"
            )

        # content_hash validation: must be 64-char lowercase hex.
        content_hash = data["content_hash"]
        if not isinstance(content_hash, str):
            raise MalformedVersionError(
                "GraphVersion.from_dict: content_hash must be a string"
            )
        if len(content_hash) != 64:
            raise MalformedVersionError(
                f"GraphVersion.from_dict: content_hash must be 64 chars, "
                f"got {len(content_hash)}"
            )
        if content_hash != content_hash.lower():
            raise MalformedVersionError(
                "GraphVersion.from_dict: content_hash must be lowercase hex"
            )
        # Verify it's actually hex.
        try:
            int(content_hash, 16)
        except ValueError:
            raise MalformedVersionError(
                "GraphVersion.from_dict: content_hash is not valid hex"
            )

        return cls(
            metadata=VersionMetadata.from_dict(incoming_metadata),
            content_hash=content_hash,
        )


# =============================================================================
# Module exports
# =============================================================================

__all__ = [
    # Dataclasses
    "VersionMetadata",
    "GraphVersion",
    # Identity computation
    "compute_node_identity",
    "compute_edge_identity",
    "compute_content_hash",
    # Helpers
    "compute_graph_id",
    "generate_build_id",
    "verify_pipeline_determinism",
    # Constants
    "SCHEMA_VERSION",
    "HASH_ALGORITHM",
    "EXPECTED_PIPELINE_SEED",
    "JSON_SERIALIZATION_OPTIONS",
    "HASH_NODES_PREFIX",
    "HASH_EDGES_PREFIX",
    "HASH_BLOB_SEPARATOR",
    # Errors
    "IncompatibleSchemaError",
    "MalformedVersionError",
]