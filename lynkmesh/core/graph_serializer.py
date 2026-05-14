# lynkmesh/core/graph_serializer.py
"""
Stage 3.1.0 — Canonical Graph Serialization

Produces a deterministic, JSON-safe payload from a finalized GraphCore.
The payload's identity layer reuses `compute_node_identity` and
`compute_edge_identity` from `graph_version.py`, ensuring serializer
output and `GraphVersion.content_hash` are derived from the same
canonicalization. They cannot drift without breaking shared invariants.

Tier: 0 (core). Allowed imports: stdlib only + lynkmesh.core.graph_version.
NOT allowed: imports from graph/, query/, exporters/, ai/, pipeline/.

Architecture spec references:
    §3 — read-only access to graph state
    §4.3 — frozen-view semantics (serializer is a frozen-copy strategy)
    §7 — exporter rules (serializer is a TIER 0 primitive, not an exporter;
          exporters live at TIER 3 and consume this serializer)
    §15 — determinism: serializer output must be byte-identical for same input
    §20 — graph versioning: serializer requires finalized GraphVersion

Determinism guarantees:
    G1 — Same input graph (post-finalization) → identical serializer output
    G2 — Output sorted lexicographically by identity JSON
    G3 — UUIDs included only as out-of-band reference fields, never in
         identity-derived sort keys
    G4 — Internal consistency check: serializer re-derives content_hash from
         its own canonicalization and verifies match with graph.version.content_hash
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Mapping, Tuple

from lynkmesh.core.graph_version import (
    GraphVersion,
    JSON_SERIALIZATION_OPTIONS,
    compute_content_hash,
    compute_edge_identity,
    compute_node_identity,
)


# =============================================================================
# Constants
# =============================================================================

# Serializer schema version. Independent from GraphVersion.schema_version.
# Bump on any breaking change to serializer output structure.
SERIALIZER_SCHEMA_VERSION: str = "3.1.0"

# Required top-level keys in serializer output, in canonical insertion order.
# Defined for documentation and consumer validation.
SERIALIZER_TOP_LEVEL_KEYS: Tuple[str, ...] = (
    "schema_version",
    "version",
    "stats",
    "nodes",
    "edges",
)


# =============================================================================
# Error types
# =============================================================================

class SerializerError(Exception):
    """Base class for serializer errors."""


class GraphNotFinalizedError(SerializerError):
    """Raised when serialization is attempted on a graph whose version
    has not been finalized."""


class SerializerConsistencyError(SerializerError):
    """Raised when the serializer's own content_hash recomputation does not
    match graph.version.content_hash. Indicates pipeline drift between
    GraphVersion finalization and serialization time."""


# =============================================================================
# Public API
# =============================================================================

def serialize_graph(graph: Any) -> Dict[str, Any]:
    """
    Produce a canonical, deterministic, JSON-safe representation of a
    finalized GraphCore.

    Args:
        graph: A finalized GraphCore instance (graph.version must succeed).

    Returns:
        A dict matching the SERIALIZER_TOP_LEVEL_KEYS schema. Suitable for
        json.dumps(result, **JSON_SERIALIZATION_OPTIONS) → byte-stable JSON.

    Raises:
        TypeError: if graph is None or lacks required GraphCore attributes.
        GraphNotFinalizedError: if graph.version raises RuntimeError.
        SerializerConsistencyError: if serializer's identity-derived
            content_hash does not match graph.version.content_hash.
    """
    # --- Defensive: validate graph shape ---------------------------------
    if graph is None:
        raise TypeError("serialize_graph: graph must not be None")
    if not hasattr(graph, "nodes") or not hasattr(graph, "edges"):
        raise TypeError(
            "serialize_graph: graph must have 'nodes' and 'edges' attributes"
        )

    # --- Require finalization (architecture spec §20.4) -------------------
    try:
        version: GraphVersion = graph.version
    except RuntimeError as exc:
        raise GraphNotFinalizedError(
            "serialize_graph: graph version is not finalized. "
            "Pipeline must call _finalize_content_hash() before serialization."
        ) from exc

    # --- Build node identity list ----------------------------------------
    # Materialize nodes once for both serialization and identity lookup.
    nodes_iter = list(graph.nodes.values())

    # nodes_map keyed by per-build UUID, for edge dereferencing during
    # identity computation. Same lookup map used by compute_content_hash.
    nodes_map: Dict[Any, Mapping[str, Any]] = {
        n.get("id"): n for n in nodes_iter if n.get("id") is not None
    }

    # Build (identity, uuid) tuples for nodes. Sort by canonical JSON of
    # identity. UUID is included as out-of-band reference, never in sort key.
    node_entries: List[Dict[str, Any]] = []
    for node in nodes_iter:
        identity = compute_node_identity(node)
        node_entries.append({
            "identity": identity,
            "uuid": node.get("id"),
        })
    node_entries.sort(
        key=lambda e: json.dumps(e["identity"], **JSON_SERIALIZATION_OPTIONS)
    )

    # --- Build edge identity list ----------------------------------------
    edge_entries: List[Dict[str, Any]] = []
    for edge in graph.edges:
        identity = compute_edge_identity(edge, nodes_map)
        edge_entries.append({
            "identity": identity,
            "uuid": edge.get("id"),
            "source_uuid": edge.get("from"),
            "target_uuid": edge.get("to"),
        })
    edge_entries.sort(
        key=lambda e: json.dumps(e["identity"], **JSON_SERIALIZATION_OPTIONS)
    )

    # --- Compute stats ----------------------------------------------------
    # Use graph.stats() directly. It's a fixed-schema dict of integer
    # counters; deterministic by construction.
    stats = graph.stats() if hasattr(graph, "stats") else {}

    # --- Assemble payload -------------------------------------------------
    payload: Dict[str, Any] = {
        "schema_version": SERIALIZER_SCHEMA_VERSION,
        "version": version.to_dict(),
        "stats": stats,
        "nodes": node_entries,
        "edges": edge_entries,
    }

    # --- Consistency invariant check (G4) ---------------------------------
    # Re-derive content_hash from the same identity stream and compare to
    # graph.version.content_hash. If they disagree, serializer and version
    # have drifted — pipeline-level invariant violation.
    recomputed_hash = compute_content_hash(
        nodes=nodes_iter,
        edges=graph.edges,
    )
    if recomputed_hash != version.content_hash:
        raise SerializerConsistencyError(
            f"serialize_graph: identity drift detected. "
            f"graph.version.content_hash={version.content_hash!r}, "
            f"serializer recomputation={recomputed_hash!r}. "
            f"This indicates graph mutation occurred after _finalize_content_hash()."
        )

    return payload


def serialize_graph_to_json(graph: Any) -> str:
    """
    Convenience: produce canonical JSON string from a finalized graph.

    Equivalent to:
        json.dumps(serialize_graph(graph), **JSON_SERIALIZATION_OPTIONS)

    Returns:
        Canonical JSON string. Byte-stable for same input graph.
    """
    return json.dumps(serialize_graph(graph), **JSON_SERIALIZATION_OPTIONS)


def get_serialized_content_hash(graph: Any) -> str:
    """
    Convenience: return the content_hash that the serialized payload commits to.

    Equivalent to graph.version.content_hash, but returned via the serializer
    to make the relationship explicit and verified.
    """
    payload = serialize_graph(graph)
    return payload["version"]["content_hash"]


# =============================================================================
# Module exports
# =============================================================================

__all__ = [
    "serialize_graph",
    "serialize_graph_to_json",
    "get_serialized_content_hash",
    "SerializerError",
    "GraphNotFinalizedError",
    "SerializerConsistencyError",
    "SERIALIZER_SCHEMA_VERSION",
    "SERIALIZER_TOP_LEVEL_KEYS",
]