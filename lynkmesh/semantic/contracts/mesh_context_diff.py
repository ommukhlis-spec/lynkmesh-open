"""Deterministic diff helpers for MeshContext Report v0.1.

This module intentionally stays pure and side-effect free.  It accepts either
``dict`` payloads or dataclass-like report objects and projects them into a
small benchmark vector that can be compared across runs without involving an
LLM.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, is_dataclass
import math
import re
from typing import Any


MESH_CONTEXT_BENCHMARK_VECTOR_SCHEMA_VERSION = "mesh_context_benchmark_vector.v0.1"
MESH_CONTEXT_DIFF_SCHEMA_VERSION = "mesh_context_diff.v0.1"

# Backward-friendly aliases for local module users.
BENCHMARK_VECTOR_SCHEMA_VERSION = MESH_CONTEXT_BENCHMARK_VECTOR_SCHEMA_VERSION
REPORT_DIFF_SCHEMA_VERSION = MESH_CONTEXT_DIFF_SCHEMA_VERSION
MESH_CONTEXT_REPORT_DIFF_SCHEMA_VERSION = MESH_CONTEXT_DIFF_SCHEMA_VERSION

_UNKNOWN = "unknown"
_REDACTED = "__unsafe_redacted__"
_CONFIDENCE_BUCKETS = (
    "0.00-0.25",
    "0.25-0.50",
    "0.50-0.75",
    "0.75-1.00",
    "out_of_range",
    _UNKNOWN,
)

_WINDOWS_ABSOLUTE_PATH_RE = re.compile(r"^[A-Za-z]:[\\/]")
_UNC_PATH_RE = re.compile(r"^\\\\")


def build_mesh_context_benchmark_vector(report: Any) -> dict[str, Any]:
    """Build a deterministic benchmark vector from a MeshContext Report.

    The extractor is deliberately tolerant of partial or synthetic fixtures.
    Missing sections are converted into stable empty/default values instead of
    raising errors.  Only deterministic counts and sanitized aggregate data are
    projected; raw paths and free-form interpretation are intentionally omitted.
    """

    payload = _to_plain(report)
    nodes = _extract_collection(
        payload,
        (
            "nodes",
            "nodes_by_uuid",
            "graph.nodes",
            "graph.nodes_by_uuid",
            "graph_summary.nodes",
            "graph_summary.nodes_by_uuid",
        ),
    )
    edges = _extract_collection(
        payload,
        (
            "edges",
            "edges_by_uuid",
            "graph.edges",
            "graph.edges_by_uuid",
            "graph_summary.edges",
            "graph_summary.edges_by_uuid",
        ),
    )

    node_count = _first_int(
        payload,
        (
            "node_count",
            "nodes_count",
            "graph.node_count",
            "graph.nodes_count",
            "graph_summary.node_count",
            "graph_summary.nodes_count",
            "summary.node_count",
            "summary.nodes_count",
            "metrics.node_count",
            "metrics.nodes_count",
        ),
        default=len(nodes),
    )
    edge_count = _first_int(
        payload,
        (
            "edge_count",
            "edges_count",
            "graph.edge_count",
            "graph.edges_count",
            "graph_summary.edge_count",
            "graph_summary.edges_count",
            "summary.edge_count",
            "summary.edges_count",
            "metrics.edge_count",
            "metrics.edges_count",
        ),
        default=len(edges),
    )

    vector = {
        "schema_version": BENCHMARK_VECTOR_SCHEMA_VERSION,
        "node_count": node_count,
        "edge_count": edge_count,
        "node_type_breakdown": _extract_or_compute_breakdown(
            payload=payload,
            explicit_paths=(
                "node_type_breakdown",
                "graph.node_type_breakdown",
                "graph_summary.node_type_breakdown",
                "summary.node_type_breakdown",
                "metrics.node_type_breakdown",
            ),
            records=nodes,
            type_keys=("type", "node_type", "kind", "category"),
        ),
        "edge_type_breakdown": _extract_or_compute_breakdown(
            payload=payload,
            explicit_paths=(
                "edge_type_breakdown",
                "graph.edge_type_breakdown",
                "graph_summary.edge_type_breakdown",
                "summary.edge_type_breakdown",
                "metrics.edge_type_breakdown",
            ),
            records=edges,
            type_keys=("type", "edge_type", "kind", "relation", "relationship"),
        ),
        "confidence_distribution": _extract_or_compute_confidence_distribution(
            payload=payload,
            nodes=nodes,
            edges=edges,
        ),
        "hotspots_count": _extract_count(
            payload,
            (
                "hotspots_count",
                "hotspot_count",
                "hotspots",
                "hotspot_candidates",
                "risk.hotspots",
                "risk_summary.hotspots",
                "summary.hotspots",
            ),
        ),
        "risk_candidate_count": _extract_count(
            payload,
            (
                "risk_candidate_count",
                "risk_candidates_count",
                "risk_candidates",
                "risks",
                "risk.candidates",
                "risk_summary.candidates",
                "risk_summary.risk_candidates",
                "summary.risk_candidates",
            ),
        ),
        "dependency_summary": _extract_dependency_summary(payload),
    }
    return _sort_mapping(vector)


def diff_mesh_context_benchmark_vectors(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
) -> dict[str, Any]:
    """Diff two MeshContext benchmark vectors deterministically."""

    before_vector = _sort_mapping(_sanitize_value(_to_plain(before)))
    after_vector = _sort_mapping(_sanitize_value(_to_plain(after)))

    before_flat = _flatten_mapping(before_vector)
    after_flat = _flatten_mapping(after_vector)

    before_keys = set(before_flat)
    after_keys = set(after_flat)
    added = sorted(after_keys - before_keys)
    removed = sorted(before_keys - after_keys)
    changed = sorted(
        key for key in (before_keys & after_keys) if before_flat[key] != after_flat[key]
    )
    unchanged_count = len(before_keys & after_keys) - len(changed)

    numeric_delta = {
        key: _numeric_delta(before_flat[key], after_flat[key])
        for key in changed
        if _is_number(before_flat[key]) and _is_number(after_flat[key])
    }

    result = {
        "schema_version": REPORT_DIFF_SCHEMA_VERSION,
        "changed": bool(added or removed or changed),
        "summary": {
            "added": len(added),
            "removed": len(removed),
            "changed": len(changed),
            "unchanged": unchanged_count,
        },
        "added": added,
        "removed": removed,
        "changed_fields": changed,
        "numeric_delta": _sort_mapping(numeric_delta),
        "before": before_vector,
        "after": after_vector,
    }
    return _sort_mapping(result)


def build_mesh_context_report_diff(before_report: Any, after_report: Any) -> dict[str, Any]:
    """Build benchmark vectors for two reports and diff them."""

    return diff_mesh_context_benchmark_vectors(
        build_mesh_context_benchmark_vector(before_report),
        build_mesh_context_benchmark_vector(after_report),
    )


def _to_plain(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return _to_plain(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): _to_plain(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_to_plain(item) for item in value]
    if isinstance(value, list):
        return [_to_plain(item) for item in value]
    return value


def _get_path(payload: Any, path: str, default: Any = None) -> Any:
    current = payload
    for part in path.split("."):
        if isinstance(current, Mapping) and part in current:
            current = current[part]
        else:
            return default
    return current


def _first_int(payload: Mapping[str, Any], paths: Sequence[str], default: int = 0) -> int:
    for path in paths:
        value = _get_path(payload, path)
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return max(value, 0)
        if isinstance(value, float) and value.is_integer():
            return max(int(value), 0)
    return max(int(default), 0)


def _extract_collection(payload: Mapping[str, Any], paths: Sequence[str]) -> list[Any]:
    for path in paths:
        value = _get_path(payload, path)
        if isinstance(value, Mapping):
            return [_to_plain(item) for _, item in sorted(value.items(), key=lambda pair: str(pair[0]))]
        if isinstance(value, list):
            return [_to_plain(item) for item in value]
        if isinstance(value, tuple):
            return [_to_plain(item) for item in value]
    return []


def _extract_or_compute_breakdown(
    *,
    payload: Mapping[str, Any],
    explicit_paths: Sequence[str],
    records: Sequence[Any],
    type_keys: Sequence[str],
) -> dict[str, int]:
    for path in explicit_paths:
        explicit = _get_path(payload, path)
        if isinstance(explicit, Mapping):
            return _normalize_count_mapping(explicit)

    counts: dict[str, int] = {}
    for record in records:
        label = _UNKNOWN
        if isinstance(record, Mapping):
            for key in type_keys:
                raw_label = record.get(key)
                if raw_label is not None:
                    label = _safe_label(raw_label)
                    break
        counts[label] = counts.get(label, 0) + 1
    return _sort_count_mapping(counts)


def _extract_or_compute_confidence_distribution(
    *,
    payload: Mapping[str, Any],
    nodes: Sequence[Any],
    edges: Sequence[Any],
) -> dict[str, int]:
    for path in (
        "confidence_distribution",
        "graph.confidence_distribution",
        "graph_summary.confidence_distribution",
        "summary.confidence_distribution",
        "metrics.confidence_distribution",
    ):
        explicit = _get_path(payload, path)
        if isinstance(explicit, Mapping):
            return _normalize_count_mapping(explicit)

    records = list(nodes) + list(edges)
    if not records:
        return {}

    counts = {bucket: 0 for bucket in _CONFIDENCE_BUCKETS}
    for record in records:
        confidence = None
        if isinstance(record, Mapping):
            for key in ("confidence", "confidence_score", "score"):
                value = record.get(key)
                if _is_number(value):
                    confidence = float(value)
                    break
        counts[_confidence_bucket(confidence)] += 1
    return _sort_count_mapping({key: value for key, value in counts.items() if value})


def _confidence_bucket(value: float | None) -> str:
    if value is None or not math.isfinite(value):
        return _UNKNOWN
    if value < 0.0 or value > 1.0:
        return "out_of_range"
    if value < 0.25:
        return "0.00-0.25"
    if value < 0.50:
        return "0.25-0.50"
    if value < 0.75:
        return "0.50-0.75"
    return "0.75-1.00"


def _extract_count(payload: Mapping[str, Any], paths: Sequence[str]) -> int:
    for path in paths:
        value = _get_path(payload, path)
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return max(value, 0)
        if isinstance(value, float) and value.is_integer():
            return max(int(value), 0)
        if isinstance(value, Mapping):
            return len(value)
        if isinstance(value, (list, tuple, set)):
            return len(value)
    return 0


def _extract_dependency_summary(payload: Mapping[str, Any]) -> dict[str, Any]:
    for path in (
        "dependency_summary",
        "dependencies.summary",
        "graph.dependency_summary",
        "graph_summary.dependency_summary",
        "summary.dependency_summary",
        "metrics.dependency_summary",
    ):
        value = _get_path(payload, path)
        if isinstance(value, Mapping):
            safe_summary = _sanitize_dependency_summary(value)
            if isinstance(safe_summary, Mapping):
                return _sort_mapping(safe_summary)
    return {}


def _sanitize_dependency_summary(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if _is_number(value):
        return value
    if value is None:
        return None
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            safe_key = _safe_label(key)
            safe_value = _sanitize_dependency_summary(item)
            if safe_value is not _REDACTED:
                result[safe_key] = safe_value
        return _sort_mapping(result)
    if isinstance(value, (list, tuple, set)):
        return len(value)
    return _REDACTED


def _normalize_count_mapping(value: Mapping[Any, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for key, item in value.items():
        if isinstance(item, bool):
            continue
        if isinstance(item, int):
            count = item
        elif isinstance(item, float) and item.is_integer():
            count = int(item)
        else:
            continue
        safe_key = _safe_label(key)
        counts[safe_key] = counts.get(safe_key, 0) + max(count, 0)
    return _sort_count_mapping(counts)


def _sort_count_mapping(value: Mapping[str, int]) -> dict[str, int]:
    return {key: int(value[key]) for key in sorted(value)}


def _sort_mapping(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _sort_mapping(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, list):
        return [_sort_mapping(item) for item in value]
    return value


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            _safe_label(key): _sanitize_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    if isinstance(value, str):
        return _safe_label(value)
    return value


def _flatten_mapping(value: Mapping[str, Any], prefix: str = "") -> dict[str, Any]:
    flattened: dict[str, Any] = {}
    for key, item in value.items():
        safe_key = _safe_label(key)
        path = f"{prefix}.{safe_key}" if prefix else safe_key
        if isinstance(item, Mapping):
            flattened.update(_flatten_mapping(item, path))
        else:
            flattened[path] = item
    return flattened


def _safe_label(value: Any) -> str:
    label = str(value) if value is not None else _UNKNOWN
    if not label:
        return _UNKNOWN
    if _is_unsafe_string(label):
        return _REDACTED
    return label


def _is_unsafe_string(value: str) -> bool:
    normalized = value.replace("\\", "/")
    return (
        bool(_WINDOWS_ABSOLUTE_PATH_RE.match(value))
        or bool(_UNC_PATH_RE.match(value))
        or normalized.startswith("/home/")
        or normalized.startswith("/Users/")
        or normalized.startswith("/mnt/")
        or normalized.startswith("/var/")
        or normalized.startswith("/tmp/")
    )


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _numeric_delta(before: int | float, after: int | float) -> int | float:
    delta = after - before
    if isinstance(delta, float) and delta.is_integer():
        return int(delta)
    return delta
