# lynkmesh/core/incremental_diff.py
"""
Stage 3.3.0 — Incremental Diff Engine

Computes deterministic diffs between two canonical GraphSerializer payloads.
Detects added, removed, and changed nodes/edges using stable identity keys
derived from semantic fields (qualified_name, type, file_path).

Tier: 0 (core). Allowed imports: stdlib only +
    lynkmesh.core.graph_serializer
    lynkmesh.core.graph_version

NOT allowed: imports from graph/, query/, exporters/, ai/, pipeline/,
             graph_cache (caller can adapt cache entries → payloads).

Architecture spec references:
    §3 — read-only access to payloads (no mutation)
    §15 — determinism: diff output byte-stable for same inputs
    §20 — graph versioning: diff operates on content_hash-keyed payloads

Diff invariants:
    D1 — Pure function: diff(A, B) returns same DiffReport across calls
    D2 — Output ordering deterministic (sorted by canonical JSON)
    D3 — Same content_hash → identical=True, all change lists empty
    D4 — Different schema_version → raises (no implicit migration)
    D5 — Stable identity keys exclude per-build UUIDs
    D6 — Diff does not touch filesystem, cache, or graph state
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Set, Tuple

from lynkmesh.core.graph_serializer import (
    SERIALIZER_SCHEMA_VERSION,
    SERIALIZER_TOP_LEVEL_KEYS,
)
from lynkmesh.core.graph_version import JSON_SERIALIZATION_OPTIONS


# =============================================================================
# Constants
# =============================================================================

DIFF_SCHEMA_VERSION: str = "3.3.0"

# Required top-level keys in diff output, in canonical insertion order.
DIFF_TOP_LEVEL_KEYS: Tuple[str, ...] = (
    "diff_schema_version",
    "computed_at",
    "before",
    "after",
    "summary",
    "nodes",
    "edges",
)

# Fields that compose the NodeKey (stable logical identity for diff).
# Must match a strict subset of identity fields produced by
# compute_node_identity in graph_version.py.
_NODE_KEY_FIELDS: Tuple[str, ...] = (
    "qualified_name",
    "type",
    "file_path",
)


# =============================================================================
# Error types
# =============================================================================

class DiffError(Exception):
    """Base class for diff errors."""


class MalformedPayloadError(DiffError):
    """Raised when a payload is missing required structure."""


class SchemaVersionMismatchError(DiffError):
    """Raised when payloads use incompatible schema versions."""


# =============================================================================
# Public types
# =============================================================================

@dataclass(frozen=True)
class DiffReport:
    """
    Result of a diff between two payloads.

    The `to_dict()` method produces a JSON-safe dict matching the
    DIFF_TOP_LEVEL_KEYS schema. Two DiffReport instances are equal iff
    their underlying data is equal (frozen dataclass auto-equality).
    """
    diff_schema_version: str
    computed_at: str
    before_meta: Dict[str, Any]
    after_meta: Dict[str, Any]
    summary: Dict[str, Any]
    nodes_added: List[Dict[str, Any]]
    nodes_removed: List[Dict[str, Any]]
    nodes_changed: List[Dict[str, Any]]
    edges_added: List[Dict[str, Any]]
    edges_removed: List[Dict[str, Any]]
    edges_changed: List[Dict[str, Any]]
    # Soft warnings (e.g., NodeKey collisions in input). Non-fatal.
    warnings: List[str] = field(default_factory=list)

    @property
    def identical(self) -> bool:
        """Convenience accessor: True iff before/after have same content_hash."""
        return bool(self.summary.get("identical", False))

    def to_dict(self) -> Dict[str, Any]:
        """JSON-safe dict representation suitable for json.dumps."""
        result: Dict[str, Any] = {
            "diff_schema_version": self.diff_schema_version,
            "computed_at": self.computed_at,
            "before": self.before_meta,
            "after": self.after_meta,
            "summary": self.summary,
            "nodes": {
                "added": self.nodes_added,
                "removed": self.nodes_removed,
                "changed": self.nodes_changed,
            },
            "edges": {
                "added": self.edges_added,
                "removed": self.edges_removed,
                "changed": self.edges_changed,
            },
        }
        if self.warnings:
            result["warnings"] = list(self.warnings)
        return result


# =============================================================================
# Internal helpers
# =============================================================================

def _now_utc_iso() -> str:
    """Current UTC time as ISO 8601. Only place we read system time."""
    return datetime.now(timezone.utc).isoformat()


def _canonical_json_key(obj: Any) -> str:
    """Sort key: canonical JSON serialization of an arbitrary value."""
    return json.dumps(obj, **JSON_SERIALIZATION_OPTIONS)


def _validate_payload(payload: Any, label: str) -> None:
    """
    Validate that a payload has the expected serializer shape.

    Args:
        payload: Object to validate.
        label: 'before' or 'after' for error messages.

    Raises:
        TypeError: if payload is None or not a dict.
        MalformedPayloadError: if required keys missing.
        SchemaVersionMismatchError: if schema_version unexpected.
    """
    if payload is None:
        raise TypeError(f"diff: {label} payload must not be None")
    if not isinstance(payload, dict):
        raise TypeError(
            f"diff: {label} payload must be a dict, "
            f"got {type(payload).__name__}"
        )
    payload_keys = set(payload.keys())
    expected_keys = set(SERIALIZER_TOP_LEVEL_KEYS)
    missing = expected_keys - payload_keys
    if missing:
        raise MalformedPayloadError(
            f"diff: {label} payload missing required keys: {sorted(missing)}"
        )
    schema = payload.get("schema_version")
    if schema != SERIALIZER_SCHEMA_VERSION:
        raise SchemaVersionMismatchError(
            f"diff: {label} payload schema_version={schema!r}, "
            f"current code expects {SERIALIZER_SCHEMA_VERSION!r}"
        )
    if not isinstance(payload.get("version"), dict):
        raise MalformedPayloadError(
            f"diff: {label} payload.version must be a dict"
        )
    if not isinstance(payload.get("nodes"), list):
        raise MalformedPayloadError(
            f"diff: {label} payload.nodes must be a list"
        )
    if not isinstance(payload.get("edges"), list):
        raise MalformedPayloadError(
            f"diff: {label} payload.edges must be a list"
        )


def _extract_node_key(identity: Mapping[str, Any]) -> Tuple[Any, ...]:
    """
    Extract stable NodeKey from a node identity dict.

    Uses _NODE_KEY_FIELDS (qualified_name, type, file_path). These fields
    survive `extra` mutation: a method whose return_type changes still
    produces the same NodeKey, classifying the mutation as "changed."
    """
    return tuple(identity.get(field_name) for field_name in _NODE_KEY_FIELDS)


def _extract_edge_key(identity: Mapping[str, Any]) -> Tuple[Any, ...]:
    """
    Extract stable EdgeKey from an edge identity dict.

    Composition:
        (source_key, target_key, edge_type, metadata.line)

    source_key and target_key are NodeKey tuples derived from the
    embedded source_identity / target_identity dicts. edge_type is the
    string. metadata.line distinguishes multiple calls between same
    source/target at different lines.
    """
    source_identity = identity.get("source_identity")
    target_identity = identity.get("target_identity")
    source_key = (
        _extract_node_key(source_identity)
        if isinstance(source_identity, dict)
        else None
    )
    target_key = (
        _extract_node_key(target_identity)
        if isinstance(target_identity, dict)
        else None
    )
    edge_type = identity.get("type")
    metadata = identity.get("metadata") or {}
    line = metadata.get("line") if isinstance(metadata, dict) else None
    return (source_key, target_key, edge_type, line)


def _entry_to_identity(entry: Mapping[str, Any], label: str) -> Mapping[str, Any]:
    """
    Extract `identity` dict from a serializer node/edge entry.

    Serializer entries are {"identity": {...}, "uuid": "...", ...}.
    """
    if not isinstance(entry, dict):
        raise MalformedPayloadError(
            f"diff: {label} entry must be a dict, got {type(entry).__name__}"
        )
    identity = entry.get("identity")
    if not isinstance(identity, dict):
        raise MalformedPayloadError(
            f"diff: {label} entry missing 'identity' dict"
        )
    return identity


def _diff_dict_fields(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
) -> List[str]:
    """
    Compare two identity dicts and return list of differing field paths.

    Recurses one level into `extra` and `metadata` sub-dicts. Reports paths
    like 'extra.return_type', 'metadata.line'. Top-level scalar differences
    reported as bare key name.

    Returns:
        Sorted list of differing field paths.
    """
    diffs: Set[str] = set()
    all_keys = set(before.keys()) | set(after.keys())
    for key in all_keys:
        bval = before.get(key)
        aval = after.get(key)
        if bval == aval:
            continue
        # Recurse one level for known nested-dict fields.
        if key in ("extra", "metadata") and isinstance(bval, dict) and isinstance(aval, dict):
            nested_keys = set(bval.keys()) | set(aval.keys())
            for nk in nested_keys:
                if bval.get(nk) != aval.get(nk):
                    diffs.add(f"{key}.{nk}")
        else:
            diffs.add(key)
    return sorted(diffs)


# =============================================================================
# Public API
# =============================================================================

def diff_payloads(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
) -> DiffReport:
    """
    Compute a deterministic diff between two canonical serializer payloads.

    Args:
        before: GraphSerializer payload (output of serialize_graph()).
        after: GraphSerializer payload.

    Returns:
        DiffReport with sorted added/removed/changed sets.

    Raises:
        TypeError: if either argument is None or not a dict.
        MalformedPayloadError: if either payload lacks required structure.
        SchemaVersionMismatchError: if schema versions don't match expected.

    The diff is a pure function: same inputs → same DiffReport, byte-stable
    when serialized via to_dict() + json.dumps with pinned options.
    """
    _validate_payload(before, "before")
    _validate_payload(after, "after")

    warnings: List[str] = []

    # --- Fast path: identical content_hash → empty diff ------------------
    before_version = before["version"]
    after_version = after["version"]
    before_hash = before_version.get("content_hash")
    after_hash = after_version.get("content_hash")
    identical = (before_hash == after_hash and before_hash is not None)

    before_metadata = before_version.get("metadata") or {}
    after_metadata = after_version.get("metadata") or {}
    before_meta_block = {
        "graph_id": before_metadata.get("graph_id"),
        "build_id": before_metadata.get("build_id"),
        "content_hash": before_hash,
    }
    after_meta_block = {
        "graph_id": after_metadata.get("graph_id"),
        "build_id": after_metadata.get("build_id"),
        "content_hash": after_hash,
    }
    same_graph_id = (
        before_meta_block["graph_id"] == after_meta_block["graph_id"]
        and before_meta_block["graph_id"] is not None
    )

    # --- Build node lookup maps ------------------------------------------
    before_nodes_by_key: Dict[Tuple[Any, ...], Mapping[str, Any]] = {}
    for entry in before["nodes"]:
        identity = _entry_to_identity(entry, "before.nodes")
        key = _extract_node_key(identity)
        if key in before_nodes_by_key:
            warnings.append(
                f"before: duplicate NodeKey {key!r}; keeping first occurrence"
            )
            continue
        before_nodes_by_key[key] = identity

    after_nodes_by_key: Dict[Tuple[Any, ...], Mapping[str, Any]] = {}
    for entry in after["nodes"]:
        identity = _entry_to_identity(entry, "after.nodes")
        key = _extract_node_key(identity)
        if key in after_nodes_by_key:
            warnings.append(
                f"after: duplicate NodeKey {key!r}; keeping first occurrence"
            )
            continue
        after_nodes_by_key[key] = identity

    # --- Compute node sets -----------------------------------------------
    before_node_keys = set(before_nodes_by_key.keys())
    after_node_keys = set(after_nodes_by_key.keys())
    added_node_keys = after_node_keys - before_node_keys
    removed_node_keys = before_node_keys - after_node_keys
    common_node_keys = before_node_keys & after_node_keys

    nodes_added: List[Dict[str, Any]] = [
        dict(after_nodes_by_key[k]) for k in added_node_keys
    ]
    nodes_removed: List[Dict[str, Any]] = [
        dict(before_nodes_by_key[k]) for k in removed_node_keys
    ]
    nodes_changed: List[Dict[str, Any]] = []
    nodes_unchanged_count = 0
    for k in common_node_keys:
        before_identity = before_nodes_by_key[k]
        after_identity = after_nodes_by_key[k]
        if before_identity == after_identity:
            nodes_unchanged_count += 1
            continue
        changed_fields = _diff_dict_fields(before_identity, after_identity)
        nodes_changed.append({
            "key": list(k),
            "before_identity": dict(before_identity),
            "after_identity": dict(after_identity),
            "changed_fields": changed_fields,
        })

    nodes_added.sort(key=_canonical_json_key)
    nodes_removed.sort(key=_canonical_json_key)
    nodes_changed.sort(key=lambda c: _canonical_json_key(c["key"]))

    # --- Build edge lookup maps ------------------------------------------
    before_edges_by_key: Dict[Tuple[Any, ...], Mapping[str, Any]] = {}
    for entry in before["edges"]:
        identity = _entry_to_identity(entry, "before.edges")
        key = _extract_edge_key(identity)
        if key in before_edges_by_key:
            warnings.append(
                f"before: duplicate EdgeKey {key!r}; keeping first occurrence"
            )
            continue
        before_edges_by_key[key] = identity

    after_edges_by_key: Dict[Tuple[Any, ...], Mapping[str, Any]] = {}
    for entry in after["edges"]:
        identity = _entry_to_identity(entry, "after.edges")
        key = _extract_edge_key(identity)
        if key in after_edges_by_key:
            warnings.append(
                f"after: duplicate EdgeKey {key!r}; keeping first occurrence"
            )
            continue
        after_edges_by_key[key] = identity

    # --- Compute edge sets -----------------------------------------------
    before_edge_keys = set(before_edges_by_key.keys())
    after_edge_keys = set(after_edges_by_key.keys())
    added_edge_keys = after_edge_keys - before_edge_keys
    removed_edge_keys = before_edge_keys - after_edge_keys
    common_edge_keys = before_edge_keys & after_edge_keys

    edges_added: List[Dict[str, Any]] = [
        dict(after_edges_by_key[k]) for k in added_edge_keys
    ]
    edges_removed: List[Dict[str, Any]] = [
        dict(before_edges_by_key[k]) for k in removed_edge_keys
    ]
    edges_changed: List[Dict[str, Any]] = []
    edges_unchanged_count = 0
    for k in common_edge_keys:
        before_identity = before_edges_by_key[k]
        after_identity = after_edges_by_key[k]
        if before_identity == after_identity:
            edges_unchanged_count += 1
            continue
        changed_fields = _diff_dict_fields(before_identity, after_identity)
        # Edge keys are nested tuples; serialize to a JSON-safe list for output.
        key_for_output: List[Any] = [
            list(k[0]) if isinstance(k[0], tuple) else k[0],  # source key
            list(k[1]) if isinstance(k[1], tuple) else k[1],  # target key
            k[2],  # edge_type
            k[3],  # line
        ]
        edges_changed.append({
            "key": key_for_output,
            "before_identity": dict(before_identity),
            "after_identity": dict(after_identity),
            "changed_fields": changed_fields,
        })

    edges_added.sort(key=_canonical_json_key)
    edges_removed.sort(key=_canonical_json_key)
    edges_changed.sort(key=lambda c: _canonical_json_key(c["key"]))

    # --- Sanity check: if content_hash matches, no diff should exist -----
    # If identical=True but we found diffs, the input is inconsistent (e.g.,
    # one payload was tampered with). Record warning, don't raise — diff is
    # observational, not authoritative.
    total_changes = (
        len(nodes_added) + len(nodes_removed) + len(nodes_changed)
        + len(edges_added) + len(edges_removed) + len(edges_changed)
    )

    if identical:
        if total_changes > 0:
            warnings.append(
                f"content_hash matches but {total_changes} change(s) detected; "
                f"input payload may be tampered"
            )
        else:
            # Same content_hash is the authoritative fast-path signal:
            # the serialized graph content is identical even if the logical
            # diff key collapses duplicate NodeKey/EdgeKey entries.
            #
            # Real pipeline payload currently has legitimate duplicate
            # logical keys (same NodeKey/EdgeKey) that are distinct serialized
            # entries. The change sets remain empty, but unchanged counts must
            # preserve payload cardinality for baseline/integration reporting.
            nodes_unchanged_count = len(before["nodes"])
            edges_unchanged_count = len(before["edges"])

    # --- Assemble summary ------------------------------------------------
    summary: Dict[str, Any] = {
        "identical": identical,
        "same_graph_id": same_graph_id,
        "nodes_added": len(nodes_added),
        "nodes_removed": len(nodes_removed),
        "nodes_changed": len(nodes_changed),
        "nodes_unchanged": nodes_unchanged_count,
        "edges_added": len(edges_added),
        "edges_removed": len(edges_removed),
        "edges_changed": len(edges_changed),
        "edges_unchanged": edges_unchanged_count,
    }
    return DiffReport(
        diff_schema_version=DIFF_SCHEMA_VERSION,
        computed_at=_now_utc_iso(),
        before_meta=before_meta_block,
        after_meta=after_meta_block,
        summary=summary,
        nodes_added=nodes_added,
        nodes_removed=nodes_removed,
        nodes_changed=nodes_changed,
        edges_added=edges_added,
        edges_removed=edges_removed,
        edges_changed=edges_changed,
        warnings=warnings,
    )


def diff_cache_entries(before: Any, after: Any) -> DiffReport:
    """
    Convenience adapter: diff two CacheEntry instances.

    Args:
        before: CacheEntry (or any object with .payload dict attribute).
        after: CacheEntry.

    Returns:
        DiffReport.

    Raises:
        TypeError: if either argument lacks a `payload` attribute.
        Any error from diff_payloads.
    """
    if not hasattr(before, "payload"):
        raise TypeError(
            f"diff_cache_entries: 'before' must have .payload attribute, "
            f"got {type(before).__name__}"
        )
    if not hasattr(after, "payload"):
        raise TypeError(
            f"diff_cache_entries: 'after' must have .payload attribute, "
            f"got {type(after).__name__}"
        )
    return diff_payloads(before.payload, after.payload)


def diff_payloads_to_json(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
) -> str:
    """
    Convenience: produce canonical JSON string of diff result.

    Equivalent to json.dumps(diff_payloads(...).to_dict(),
                             **JSON_SERIALIZATION_OPTIONS).

    Note: the `computed_at` timestamp varies across calls, so the JSON is
    NOT byte-stable across invocations. For byte-stability tests, compare
    to_dict() output directly after stripping computed_at.
    """
    report = diff_payloads(before, after)
    return json.dumps(report.to_dict(), **JSON_SERIALIZATION_OPTIONS)


# =============================================================================
# Module exports
# =============================================================================

__all__ = [
    "diff_payloads",
    "diff_cache_entries",
    "diff_payloads_to_json",
    "DiffReport",
    "DiffError",
    "MalformedPayloadError",
    "SchemaVersionMismatchError",
    "DIFF_SCHEMA_VERSION",
    "DIFF_TOP_LEVEL_KEYS",
]