"""MeshContext AI Context Pack v0.1 contract helpers.

The AI Context Pack is a deterministic, token-conscious projection of
MeshContext Report v0.1 intended for direct AI/MCP-client consumption.  This
module deliberately stays pure and side-effect free: it accepts dict-like or
simple dataclass-like reports, builds a compact JSON-serializable payload, and
never performs filesystem or network I/O.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field, is_dataclass
import json
import math
import re
from typing import Any


MESH_CONTEXT_AI_PACK_SCHEMA_VERSION = "mesh_context_ai_pack.v0.1"
MESH_CONTEXT_AI_PACK_PURPOSE = "ai_consumption"
MESH_CONTEXT_AI_PACK_TOKEN_ESTIMATOR = "deterministic_char_heuristic_v0.1"
MESH_CONTEXT_AI_PACK_SOURCE_REPORT_SCHEMA_VERSION = "mesh_context_report.v0.1"

SUPPORTED_MESH_CONTEXT_AI_PACK_PROFILES = ("compact", "balanced", "expanded")

_UNKNOWN = "unknown"
_REDACTED = "__unsafe_redacted__"

_WINDOWS_ABSOLUTE_PATH_RE = re.compile(r"^[A-Za-z]:[\\/]")
_UNC_PATH_RE = re.compile(r"^\\\\")
_POSIX_PRIVATE_PATH_RE = re.compile(
    r"^/(?:home|Users|mnt|private|tmp|var|etc|root)(?:/|$)",
    re.IGNORECASE,
)

_PROFILE_LIMITS: dict[str, dict[str, int]] = {
    "compact": {
        "hotspots": 5,
        "risk_candidates": 5,
        "evidence_nodes": 12,
        "evidence_edges": 12,
        "dependencies": 8,
    },
    "balanced": {
        "hotspots": 15,
        "risk_candidates": 15,
        "evidence_nodes": 40,
        "evidence_edges": 40,
        "dependencies": 20,
    },
    "expanded": {
        "hotspots": 50,
        "risk_candidates": 50,
        "evidence_nodes": 120,
        "evidence_edges": 120,
        "dependencies": 50,
    },
}


@dataclass(frozen=True)
class MeshContextBudget:
    """Deterministic token budget metadata for an AI Context Pack."""

    profile: str
    estimated_input_tokens: int = 0
    estimated_output_tokens: int = 0
    estimated_source_report_tokens: int = 0
    estimated_token_reduction_percent: float = 0.0
    estimator: str = MESH_CONTEXT_AI_PACK_TOKEN_ESTIMATOR

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MeshContextAITaskGuide:
    """Machine-readable task guidance for downstream AI clients."""

    best_for: list[str] = field(
        default_factory=lambda: [
            "architecture_overview",
            "impact_analysis",
            "risk_review",
            "refactor_planning",
        ]
    )
    not_enough_for: list[str] = field(
        default_factory=lambda: [
            "line_level_code_fix_without_source",
            "business_rule_validation_without_domain_input",
        ]
    )
    recommended_response_style: str = (
        "cite evidence IDs and avoid unsupported inference"
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MeshContextAIContextPack:
    """Typed top-level shape for MeshContext AI Context Pack v0.1."""

    schema_version: str
    source_report_schema_version: str
    profile: str
    purpose: str
    project_identity: dict[str, Any]
    context_budget: dict[str, Any]
    ai_task_guide: dict[str, Any]
    executive_context: dict[str, Any]
    architecture_context: dict[str, Any]
    hotspot_context: dict[str, Any]
    risk_context: dict[str, Any]
    dependency_context: dict[str, Any]
    evidence_index: dict[str, Any]
    omissions: dict[str, Any]
    guardrails: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_mesh_context_ai_pack(report: Any, profile: str = "compact") -> dict[str, Any]:
    """Build a deterministic AI-ready context pack from a MeshContext Report.

    The builder accepts partial synthetic fixtures as well as richer report
    objects.  Missing optional sections become stable empty/default structures.
    It performs deterministic selection, path redaction, and approximate token
    estimation without using an LLM or touching the filesystem.
    """

    if profile not in SUPPORTED_MESH_CONTEXT_AI_PACK_PROFILES:
        supported = ", ".join(SUPPORTED_MESH_CONTEXT_AI_PACK_PROFILES)
        raise ValueError(f"Unsupported MeshContext AI pack profile: {profile!r}. Supported: {supported}")

    payload = _to_plain(report)
    limits = _PROFILE_LIMITS[profile]

    nodes = _extract_collection(
        payload,
        (
            "nodes",
            "nodes_by_uuid",
            "graph_facts.nodes",
            "graph_facts.nodes_by_uuid",
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
            "graph_facts.edges",
            "graph_facts.edges_by_uuid",
            "graph.edges",
            "graph.edges_by_uuid",
            "graph_summary.edges",
            "graph_summary.edges_by_uuid",
        ),
    )
    hotspots = _extract_collection(
        payload,
        (
            "hotspots",
            "hotspot_candidates",
            "risk.hotspots",
            "risk_summary.hotspots",
            "summary.hotspots",
        ),
    )
    risk_candidates = _extract_collection(
        payload,
        (
            "risk_candidates",
            "risks",
            "risk.candidates",
            "risk_summary.candidates",
            "risk_summary.risk_candidates",
            "summary.risk_candidates",
        ),
    )

    node_count = _first_int(
        payload,
        (
            "node_count",
            "nodes_count",
            "graph.node_count",
            "graph.nodes_count",
            "graph_facts.node_count",
            "graph_facts.nodes_count",
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
            "graph_facts.edge_count",
            "graph_facts.edges_count",
            "graph_summary.edge_count",
            "graph_summary.edges_count",
            "summary.edge_count",
            "summary.edges_count",
            "metrics.edge_count",
            "metrics.edges_count",
        ),
        default=len(edges),
    )

    node_type_breakdown = _extract_or_compute_breakdown(
        payload=payload,
        explicit_paths=(
            "node_type_breakdown",
            "graph.node_type_breakdown",
            "graph_facts.node_type_breakdown",
            "graph_summary.node_type_breakdown",
            "summary.node_type_breakdown",
            "metrics.node_type_breakdown",
        ),
        records=nodes,
        type_keys=("type", "node_type", "kind", "category"),
    )
    edge_type_breakdown = _extract_or_compute_breakdown(
        payload=payload,
        explicit_paths=(
            "edge_type_breakdown",
            "graph.edge_type_breakdown",
            "graph_facts.edge_type_breakdown",
            "graph_summary.edge_type_breakdown",
            "summary.edge_type_breakdown",
            "metrics.edge_type_breakdown",
        ),
        records=edges,
        type_keys=("type", "edge_type", "kind", "relation", "relationship"),
    )
    confidence_distribution = _first_mapping(
        payload,
        (
            "confidence_distribution",
            "graph.confidence_distribution",
            "graph_facts.confidence_distribution",
            "graph_summary.confidence_distribution",
            "summary.confidence_distribution",
            "metrics.confidence_distribution",
        ),
    )
    dependency_summary = _extract_dependency_summary(payload, limit=limits["dependencies"])

    hotspot_items = _build_context_items(
        records=hotspots,
        kind="hotspot",
        limit=limits["hotspots"],
    )
    risk_items = _build_context_items(
        records=risk_candidates,
        kind="risk",
        limit=limits["risk_candidates"],
    )
    evidence_index = _build_evidence_index(
        nodes=nodes,
        edges=edges,
        profile=profile,
        node_limit=limits["evidence_nodes"],
        edge_limit=limits["evidence_edges"],
    )

    source_schema_version = str(
        _first_value(
            payload,
            (
                "schema_version",
                "report_schema_version",
                "mesh_context_report_schema_version",
            ),
            MESH_CONTEXT_AI_PACK_SOURCE_REPORT_SCHEMA_VERSION,
        )
    )

    pack = {
        "schema_version": MESH_CONTEXT_AI_PACK_SCHEMA_VERSION,
        "source_report_schema_version": source_schema_version,
        "profile": profile,
        "purpose": MESH_CONTEXT_AI_PACK_PURPOSE,
        "project_identity": _extract_project_identity(payload),
        "context_budget": MeshContextBudget(profile=profile).to_dict(),
        "ai_task_guide": MeshContextAITaskGuide().to_dict(),
        "executive_context": {
            "node_count": node_count,
            "edge_count": edge_count,
            "node_type_breakdown": node_type_breakdown,
            "edge_type_breakdown": edge_type_breakdown,
            "hotspots_count": len(hotspots),
            "risk_candidate_count": len(risk_candidates),
            "confidence_distribution": confidence_distribution,
        },
        "architecture_context": _extract_architecture_context(
            payload=payload,
            node_type_breakdown=node_type_breakdown,
            nodes=nodes,
            profile=profile,
        ),
        "hotspot_context": {
            "included_count": len(hotspot_items),
            "total_count": len(hotspots),
            "items": hotspot_items,
        },
        "risk_context": {
            "included_count": len(risk_items),
            "total_count": len(risk_candidates),
            "items": risk_items,
        },
        "dependency_context": dependency_summary,
        "evidence_index": evidence_index,
        "omissions": _build_omissions(
            profile=profile,
            hotspots_total=len(hotspots),
            hotspots_included=len(hotspot_items),
            risks_total=len(risk_candidates),
            risks_included=len(risk_items),
            nodes_total=len(nodes),
            nodes_included=len(evidence_index["nodes"]),
            edges_total=len(edges),
            edges_included=len(evidence_index["edges"]),
        ),
        "guardrails": _build_guardrails(),
    }

    pack = _sort_mapping(_sanitize_value(pack))
    pack["context_budget"] = _build_context_budget(
        source_report=payload,
        pack=pack,
        profile=profile,
    )
    return _sort_mapping(_sanitize_value(pack))


def estimate_mesh_context_tokens(payload: Any) -> int:
    """Estimate token footprint using a deterministic char-count heuristic.

    v0.1 intentionally avoids tokenizer dependencies.  The estimate is meant
    for stable relative comparisons, not model-specific billing.
    """

    plain = _to_plain(payload)
    serialized = json.dumps(
        plain,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return max(0, int(math.ceil(len(serialized) / 4)))


def find_unsafe_ai_pack_strings(payload: Any) -> list[str]:
    """Return sorted unsafe absolute/private path-like strings in a payload."""

    findings: set[str] = set()

    def visit(value: Any) -> None:
        if isinstance(value, Mapping):
            for key, item in value.items():
                if isinstance(key, str) and _is_unsafe_path_string(key):
                    findings.add(key)
                visit(item)
            return
        if isinstance(value, (list, tuple)):
            for item in value:
                visit(item)
            return
        if isinstance(value, str) and _is_unsafe_path_string(value):
            findings.add(value)

    visit(_to_plain(payload))
    return sorted(findings)


def _build_context_budget(
    *,
    source_report: Any,
    pack: Mapping[str, Any],
    profile: str,
) -> dict[str, Any]:
    source_tokens = estimate_mesh_context_tokens(source_report)
    budget = MeshContextBudget(profile=profile).to_dict()
    candidate = dict(pack)

    # The estimate includes the final budget itself.  Iterate to a stable value
    # because the number of digits in the estimate can slightly affect size.
    previous_input_tokens = -1
    input_tokens = 0
    for _ in range(10):
        budget["estimated_input_tokens"] = input_tokens
        budget["estimated_source_report_tokens"] = source_tokens
        budget["estimated_token_reduction_percent"] = _token_reduction_percent(
            source_tokens,
            input_tokens,
        )
        candidate["context_budget"] = budget
        input_tokens = estimate_mesh_context_tokens(candidate)
        if input_tokens == previous_input_tokens:
            break
        previous_input_tokens = input_tokens

    budget["estimated_input_tokens"] = input_tokens
    budget["estimated_source_report_tokens"] = source_tokens
    budget["estimated_output_tokens"] = 0
    budget["estimated_token_reduction_percent"] = _token_reduction_percent(
        source_tokens,
        input_tokens,
    )
    budget["estimator"] = MESH_CONTEXT_AI_PACK_TOKEN_ESTIMATOR
    return _sort_mapping(budget)


def _token_reduction_percent(source_tokens: int, pack_tokens: int) -> float:
    if source_tokens <= 0:
        return 0.0
    reduction = ((source_tokens - pack_tokens) / source_tokens) * 100.0
    return round(max(-100.0, min(100.0, reduction)), 2)


def _extract_project_identity(payload: Mapping[str, Any]) -> dict[str, Any]:
    display_name = _first_value(
        payload,
        (
            "project.display_name",
            "project.name",
            "metadata.display_name",
            "display_name",
            "name",
        ),
        _UNKNOWN,
    )
    graph_id = _first_value(
        payload,
        (
            "graph_id",
            "project.graph_id",
            "metadata.graph_id",
            "graph.graph_id",
        ),
        _UNKNOWN,
    )
    build_id = _first_value(
        payload,
        (
            "build_id",
            "build.build_id",
            "build.id",
            "metadata.build_id",
        ),
        _UNKNOWN,
    )
    content_hash = _first_value(
        payload,
        (
            "content_hash",
            "build.content_hash",
            "metadata.content_hash",
            "graph.content_hash",
        ),
        _UNKNOWN,
    )

    return _sort_mapping(
        {
            "display_name": _safe_scalar(display_name),
            "graph_id": _safe_scalar(graph_id),
            "build_id": _safe_scalar(build_id),
            "content_hash": _safe_scalar(content_hash),
            "language_hints": _safe_list(
                _first_value(
                    payload,
                    (
                        "project.language_hints",
                        "metadata.language_hints",
                        "language_hints",
                        "languages",
                    ),
                    [],
                )
            ),
            "framework_hints": _safe_list(
                _first_value(
                    payload,
                    (
                        "project.framework_hints",
                        "metadata.framework_hints",
                        "framework_hints",
                        "frameworks",
                    ),
                    [],
                )
            ),
        }
    )


def _extract_architecture_context(
    *,
    payload: Mapping[str, Any],
    node_type_breakdown: Mapping[str, int],
    nodes: Sequence[Any],
    profile: str,
) -> dict[str, Any]:
    explicit = _first_mapping(
        payload,
        (
            "architecture_context",
            "architecture",
            "summary.architecture_context",
            "graph_summary.architecture_context",
        ),
    )
    if explicit:
        return _sort_mapping(
            {
                "dominant_components": _safe_list(explicit.get("dominant_components", [])),
                "entrypoint_candidates": _safe_list(explicit.get("entrypoint_candidates", [])),
                "service_candidates": _safe_list(explicit.get("service_candidates", [])),
                "data_access_candidates": _safe_list(explicit.get("data_access_candidates", [])),
                "cross_cutting_candidates": _safe_list(explicit.get("cross_cutting_candidates", [])),
            }
        )

    dominant_components = [
        {"type": key, "count": value}
        for key, value in sorted(
            node_type_breakdown.items(),
            key=lambda pair: (-pair[1], pair[0]),
        )[:5]
    ]
    entrypoint_candidates = _select_nodes_by_keywords(
        nodes,
        keywords=("controller", "route", "endpoint", "handler", "command"),
        limit=5 if profile == "compact" else 15,
    )
    service_candidates = _select_nodes_by_keywords(
        nodes,
        keywords=("service", "manager", "usecase", "use_case"),
        limit=5 if profile == "compact" else 15,
    )
    data_access_candidates = _select_nodes_by_keywords(
        nodes,
        keywords=("repository", "model", "dao", "query", "database"),
        limit=5 if profile == "compact" else 15,
    )

    return _sort_mapping(
        {
            "dominant_components": dominant_components,
            "entrypoint_candidates": entrypoint_candidates,
            "service_candidates": service_candidates,
            "data_access_candidates": data_access_candidates,
            "cross_cutting_candidates": [],
        }
    )


def _build_context_items(
    *,
    records: Sequence[Any],
    kind: str,
    limit: int,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for rank, record in enumerate(_stable_record_order(records), start=1):
        if len(items) >= limit:
            break
        if not isinstance(record, Mapping):
            continue
        raw_id = _record_id(record)
        safe_id = _safe_identifier(raw_id)
        if not safe_id:
            safe_id = f"{kind}:{rank}"
        elif not str(safe_id).startswith(f"{kind}:"):
            safe_id = f"{kind}:{safe_id}"

        label = _safe_scalar(
            _first_record_value(record, ("label", "name", "display_name", "symbol", "id"), safe_id)
        )
        evidence_ids = _extract_evidence_ids(record)
        if not evidence_ids and raw_id:
            evidence_ids = [f"node:{_safe_identifier(raw_id)}"]

        item = {
            "id": safe_id,
            "label": label,
            "kind": kind,
            "rank": rank,
            "signals": _extract_signals(record),
            "evidence_ids": sorted(set(evidence_ids)),
        }
        items.append(_sort_mapping(_sanitize_value(item)))
    return items


def _build_evidence_index(
    *,
    nodes: Sequence[Any],
    edges: Sequence[Any],
    profile: str,
    node_limit: int,
    edge_limit: int,
) -> dict[str, Any]:
    indexed_nodes: dict[str, Any] = {}
    for record in _stable_record_order(nodes):
        if len(indexed_nodes) >= node_limit:
            break
        item = _build_evidence_item(record, kind="node")
        if item is not None:
            indexed_nodes[item["id"]] = item

    indexed_edges: dict[str, Any] = {}
    for record in _stable_record_order(edges):
        if len(indexed_edges) >= edge_limit:
            break
        item = _build_evidence_item(record, kind="edge")
        if item is not None:
            indexed_edges[item["id"]] = item

    sections = {
        "executive_context": {
            "id": "section:executive_context",
            "kind": "section",
            "reason": "compact_project_summary",
        },
        "architecture_context": {
            "id": "section:architecture_context",
            "kind": "section",
            "reason": "high_signal_architecture_context",
        },
        "hotspot_context": {
            "id": "section:hotspot_context",
            "kind": "section",
            "reason": "ranked_hotspot_candidates",
        },
        "risk_context": {
            "id": "section:risk_context",
            "kind": "section",
            "reason": "ranked_risk_candidates",
        },
    }

    return _sort_mapping(
        {
            "nodes": indexed_nodes,
            "edges": indexed_edges,
            "sections": sections,
            "profile": profile,
        }
    )


def _build_evidence_item(record: Any, kind: str) -> dict[str, Any] | None:
    if not isinstance(record, Mapping):
        return None
    raw_id = _record_id(record)
    safe_id = _safe_identifier(raw_id)
    if not safe_id:
        return None
    evidence_id = safe_id if str(safe_id).startswith(f"{kind}:") else f"{kind}:{safe_id}"
    item = {
        "id": evidence_id,
        "kind": kind,
        "label": _safe_scalar(
            _first_record_value(record, ("label", "name", "display_name", "symbol", "id"), evidence_id)
        ),
        "type": _safe_scalar(
            _first_record_value(
                record,
                ("type", f"{kind}_type", "kind", "category", "relation", "relationship"),
                _UNKNOWN,
            )
        ),
        "confidence": _safe_scalar(
            _first_record_value(record, ("confidence", "confidence_class", "score"), _UNKNOWN)
        ),
        "reason": f"selected_from_{kind}_evidence_index",
    }
    return _sort_mapping(_sanitize_value(item))


def _build_omissions(
    *,
    profile: str,
    hotspots_total: int,
    hotspots_included: int,
    risks_total: int,
    risks_included: int,
    nodes_total: int,
    nodes_included: int,
    edges_total: int,
    edges_included: int,
) -> dict[str, Any]:
    truncated: list[str] = []
    if hotspots_included < hotspots_total:
        truncated.append("hotspot_context.items")
    if risks_included < risks_total:
        truncated.append("risk_context.items")
    if nodes_included < nodes_total:
        truncated.append("evidence_index.nodes")
    if edges_included < edges_total:
        truncated.append("evidence_index.edges")

    omitted = ["raw_source_files", "full_raw_node_listing", "full_raw_edge_listing"]
    return _sort_mapping(
        {
            "profile_limits_applied": bool(truncated or profile != "expanded"),
            "omitted_sections": omitted,
            "truncated_sections": truncated,
            "reason": f"{profile} profile selected",
        }
    )


def _build_guardrails() -> dict[str, bool]:
    return {
        "deterministic_facts_only": True,
        "contains_llm_inference": False,
        "llm_interpretation_not_included": True,
        "must_cite_evidence_ids": True,
        "do_not_infer_business_logic_without_evidence": True,
        "do_not_assume_unseen_source_code": True,
    }


def _extract_dependency_summary(payload: Mapping[str, Any], limit: int) -> dict[str, Any]:
    explicit = _first_mapping(
        payload,
        (
            "dependency_context",
            "dependency_summary",
            "dependencies",
            "graph.dependency_summary",
            "graph_facts.dependency_summary",
            "graph_summary.dependency_summary",
            "summary.dependency_summary",
            "metrics.dependency_summary",
        ),
    )
    if not explicit:
        return {
            "summary": {},
            "important_internal_dependencies": [],
            "important_external_dependencies": [],
        }

    summary = {
        key: value
        for key, value in explicit.items()
        if key
        not in {
            "important_internal_dependencies",
            "important_external_dependencies",
            "internal_dependencies",
            "external_dependencies",
            "top_dependencies",
        }
    }
    internal = _dependency_list(
        explicit.get("important_internal_dependencies")
        or explicit.get("internal_dependencies")
        or explicit.get("top_internal_dependencies")
        or explicit.get("top_dependencies")
        or [],
        limit=limit,
    )
    external = _dependency_list(
        explicit.get("important_external_dependencies")
        or explicit.get("external_dependencies")
        or explicit.get("top_external_dependencies")
        or [],
        limit=limit,
    )
    return _sort_mapping(
        {
            "summary": _sort_mapping(_sanitize_value(summary)),
            "important_internal_dependencies": internal,
            "important_external_dependencies": external,
        }
    )


def _dependency_list(value: Any, limit: int) -> list[Any]:
    plain = _to_plain(value)
    if isinstance(plain, Mapping):
        records = [
            {"id": str(key), "weight": item}
            for key, item in sorted(plain.items(), key=lambda pair: str(pair[0]))
        ]
    elif isinstance(plain, list):
        records = plain
    else:
        records = []
    return [_sanitize_value(item) for item in records[:limit]]


def _extract_or_compute_breakdown(
    *,
    payload: Mapping[str, Any],
    explicit_paths: Sequence[str],
    records: Sequence[Any],
    type_keys: Sequence[str],
) -> dict[str, int]:
    explicit = _first_mapping(payload, explicit_paths)
    if explicit:
        return _normalize_int_mapping(explicit)

    counts: dict[str, int] = {}
    for record in records:
        if not isinstance(record, Mapping):
            continue
        label = None
        for key in type_keys:
            value = record.get(key)
            if isinstance(value, str) and value:
                label = _safe_scalar(value)
                break
        if not label:
            label = _UNKNOWN
        counts[str(label)] = counts.get(str(label), 0) + 1
    return _sort_mapping(counts)


def _normalize_int_mapping(value: Mapping[str, Any]) -> dict[str, int]:
    result: dict[str, int] = {}
    for key, item in value.items():
        if isinstance(item, bool):
            continue
        if isinstance(item, int):
            result[_safe_scalar(key)] = max(item, 0)
        elif isinstance(item, float) and item.is_integer():
            result[_safe_scalar(key)] = max(int(item), 0)
    return _sort_mapping(result)


def _extract_collection(payload: Mapping[str, Any], paths: Sequence[str]) -> list[Any]:
    for path in paths:
        value = _get_path(payload, path)
        if isinstance(value, Mapping):
            return [
                _with_mapping_key(item, key)
                for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            ]
        if isinstance(value, list):
            return [_to_plain(item) for item in value]
        if isinstance(value, tuple):
            return [_to_plain(item) for item in value]
    return []


def _with_mapping_key(item: Any, key: Any) -> Any:
    plain = _to_plain(item)
    if isinstance(plain, Mapping) and "id" not in plain:
        clone = dict(plain)
        clone["id"] = str(key)
        return clone
    return plain


def _stable_record_order(records: Sequence[Any]) -> list[Any]:
    return sorted(records, key=lambda item: json.dumps(_to_plain(item), sort_keys=True, default=str))


def _select_nodes_by_keywords(
    nodes: Sequence[Any],
    *,
    keywords: Sequence[str],
    limit: int,
) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for record in _stable_record_order(nodes):
        if not isinstance(record, Mapping):
            continue
        haystack = " ".join(str(value) for value in record.values()).lower()
        if not any(keyword in haystack for keyword in keywords):
            continue
        item = _build_evidence_item(record, kind="node")
        if item is not None:
            matches.append(item)
        if len(matches) >= limit:
            break
    return matches


def _extract_signals(record: Mapping[str, Any]) -> dict[str, Any]:
    explicit = record.get("signals")
    if isinstance(explicit, Mapping):
        return _sort_mapping(_sanitize_value(dict(explicit)))

    allowed = (
        "fan_in",
        "fan_out",
        "degree",
        "score",
        "confidence",
        "risk_level",
        "reason",
        "type",
        "node_type",
        "edge_type",
    )
    signals = {
        key: record[key]
        for key in allowed
        if key in record and isinstance(record[key], (str, int, float, bool))
    }
    return _sort_mapping(_sanitize_value(signals))


def _extract_evidence_ids(record: Mapping[str, Any]) -> list[str]:
    values = record.get("evidence_ids") or record.get("evidence") or []
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, Sequence):
        return []
    result: list[str] = []
    for value in values:
        safe = _safe_identifier(value)
        if safe:
            result.append(str(safe))
    return sorted(set(result))


def _record_id(record: Mapping[str, Any]) -> str | None:
    value = _first_record_value(
        record,
        ("id", "uuid", "node_id", "edge_id", "stable_id", "qualified_name", "name", "label"),
        None,
    )
    if value is None:
        return None
    return str(value)


def _safe_identifier(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    if not text or _is_unsafe_path_string(text):
        return None
    return _safe_scalar(text)


def _safe_scalar(value: Any) -> str:
    text = str(value)
    if _is_unsafe_path_string(text):
        return _REDACTED
    return text


def _safe_list(value: Any) -> list[Any]:
    plain = _to_plain(value)
    if not isinstance(plain, (list, tuple)):
        return []
    return [_sanitize_value(item) for item in plain]


def _first_value(payload: Mapping[str, Any], paths: Sequence[str], default: Any = None) -> Any:
    for path in paths:
        value = _get_path(payload, path)
        if value is not None:
            return value
    return default


def _first_record_value(record: Mapping[str, Any], keys: Sequence[str], default: Any = None) -> Any:
    for key in keys:
        if key in record and record[key] is not None:
            return record[key]
    return default


def _first_mapping(payload: Mapping[str, Any], paths: Sequence[str]) -> dict[str, Any]:
    for path in paths:
        value = _get_path(payload, path)
        if isinstance(value, Mapping):
            return _sort_mapping(_sanitize_value(dict(value)))
    return {}


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


def _get_path(payload: Any, path: str, default: Any = None) -> Any:
    current = payload
    for part in path.split("."):
        if isinstance(current, Mapping) and part in current:
            current = current[part]
        else:
            return default
    return current


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


def _sort_mapping(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _sort_mapping(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, list):
        return [_sort_mapping(item) for item in value]
    return value


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            safe_key = _REDACTED if isinstance(key, str) and _is_unsafe_path_string(key) else str(key)
            sanitized[safe_key] = _sanitize_value(item)
        return _sort_mapping(sanitized)
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    if isinstance(value, tuple):
        return [_sanitize_value(item) for item in value]
    if isinstance(value, str) and _is_unsafe_path_string(value):
        return _REDACTED
    return value


def _is_unsafe_path_string(value: str) -> bool:
    if not value:
        return False
    return bool(
        _WINDOWS_ABSOLUTE_PATH_RE.match(value)
        or _UNC_PATH_RE.match(value)
        or _POSIX_PRIVATE_PATH_RE.match(value)
    )
