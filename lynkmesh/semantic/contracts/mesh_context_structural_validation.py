"""MeshContext structural validation v0.1 helpers.

This module validates that graph-derived facts remain structurally consistent
across LynkMesh's deterministic context layers:

    serialized graph payload -> MeshContext Report -> AI Context Pack -> token benchmark

The validator is intentionally pure and side-effect free.  It does not read
files, write files, call LynkMesh runtime graph builders, or invoke an LLM.
It only inspects JSON-like payloads supplied by callers/tests and returns a
stable JSON-serializable validation report.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field, is_dataclass
import re
from typing import Any


MESH_CONTEXT_STRUCTURAL_VALIDATION_SCHEMA_VERSION = (
    "mesh_context_structural_validation.v0.1"
)

_UNKNOWN = "unknown"
_REDACTED = "__unsafe_redacted__"

_WINDOWS_ABSOLUTE_PATH_RE = re.compile(r"^[A-Za-z]:[\\/]")
_UNC_PATH_RE = re.compile(r"^\\\\")
_POSIX_PRIVATE_PATH_RE = re.compile(
    r"^/(?:home|Users|mnt|private|tmp|var|etc|root)(?:/|$)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class MeshContextStructuralCheck:
    """One deterministic structural validation check."""

    name: str
    status: str
    expected: Any = None
    actual: Any = None
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MeshContextStructuralValidation:
    """Top-level structural validation report."""

    schema_version: str
    is_valid: bool
    checked_layers: list[str]
    graph_payload_facts: dict[str, Any]
    report_facts: dict[str, Any]
    ai_pack_facts: dict[str, Any]
    token_benchmark_facts: dict[str, Any]
    checks: list[dict[str, Any]] = field(default_factory=list)
    guardrails: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_mesh_context_structural_validation(
    *,
    graph_payload: Any | None = None,
    mesh_context_report: Any | None = None,
    ai_context_pack: Any | None = None,
    token_benchmark: Any | None = None,
) -> dict[str, Any]:
    """Validate structural consistency across MeshContext payload layers.

    All arguments are optional to make the helper useful for partial fixtures.
    Checks that cannot be evaluated are marked ``skipped`` rather than failing.
    A validation is considered valid when there are no failed checks.
    """

    graph_plain = _sanitize_value(_to_plain(graph_payload)) if graph_payload is not None else None
    report_plain = _sanitize_value(_to_plain(mesh_context_report)) if mesh_context_report is not None else None
    ai_pack_plain = _sanitize_value(_to_plain(ai_context_pack)) if ai_context_pack is not None else None
    benchmark_plain = _sanitize_value(_to_plain(token_benchmark)) if token_benchmark is not None else None

    graph_facts = _extract_graph_payload_facts(graph_plain) if graph_plain is not None else {}
    report_facts = _extract_report_facts(report_plain) if report_plain is not None else {}
    ai_pack_facts = _extract_ai_pack_facts(ai_pack_plain) if ai_pack_plain is not None else {}
    token_benchmark_facts = (
        _extract_token_benchmark_facts(benchmark_plain) if benchmark_plain is not None else {}
    )

    checks: list[dict[str, Any]] = []
    checks.extend(_count_consistency_checks("node_count", graph_facts, report_facts, ai_pack_facts))
    checks.extend(_count_consistency_checks("edge_count", graph_facts, report_facts, ai_pack_facts))
    checks.extend(
        _breakdown_consistency_checks(
            "node_type_breakdown",
            graph_facts,
            report_facts,
            ai_pack_facts,
        )
    )
    checks.extend(
        _breakdown_consistency_checks(
            "edge_type_breakdown",
            graph_facts,
            report_facts,
            ai_pack_facts,
        )
    )
    checks.extend(_llm_guardrail_checks(report_plain, ai_pack_plain, benchmark_plain))
    checks.extend(_token_benchmark_calibration_checks(token_benchmark_facts))

    failed = [check for check in checks if check.get("status") == "failed"]
    checked_layers = []
    if graph_plain is not None:
        checked_layers.append("graph_payload")
    if report_plain is not None:
        checked_layers.append("mesh_context_report")
    if ai_pack_plain is not None:
        checked_layers.append("ai_context_pack")
    if benchmark_plain is not None:
        checked_layers.append("token_benchmark")

    validation = MeshContextStructuralValidation(
        schema_version=MESH_CONTEXT_STRUCTURAL_VALIDATION_SCHEMA_VERSION,
        is_valid=not failed,
        checked_layers=checked_layers,
        graph_payload_facts=graph_facts,
        report_facts=report_facts,
        ai_pack_facts=ai_pack_facts,
        token_benchmark_facts=token_benchmark_facts,
        checks=checks,
        guardrails={
            "contains_llm_inference": False,
            "deterministic_checks_only": True,
            "filesystem_io_not_performed": True,
            "runtime_graph_extraction_not_performed": True,
        },
    ).to_dict()
    return _sort_mapping(_sanitize_value(validation))


def find_unsafe_structural_validation_strings(payload: Any) -> list[str]:
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


def _count_consistency_checks(
    field_name: str,
    graph_facts: Mapping[str, Any],
    report_facts: Mapping[str, Any],
    ai_pack_facts: Mapping[str, Any],
) -> list[dict[str, Any]]:
    return [
        _compare_check(
            name=f"graph_payload_to_report_{field_name}_matches",
            expected=graph_facts.get(field_name),
            actual=report_facts.get(field_name),
            missing_message="graph payload or report count unavailable",
        ),
        _compare_check(
            name=f"report_to_ai_pack_{field_name}_matches",
            expected=report_facts.get(field_name),
            actual=ai_pack_facts.get(field_name),
            missing_message="report or AI pack count unavailable",
        ),
    ]


def _breakdown_consistency_checks(
    field_name: str,
    graph_facts: Mapping[str, Any],
    report_facts: Mapping[str, Any],
    ai_pack_facts: Mapping[str, Any],
) -> list[dict[str, Any]]:
    return [
        _compare_check(
            name=f"graph_payload_to_report_{field_name}_matches",
            expected=graph_facts.get(field_name),
            actual=report_facts.get(field_name),
            missing_message="graph payload or report breakdown unavailable",
        ),
        _compare_check(
            name=f"report_to_ai_pack_{field_name}_matches",
            expected=report_facts.get(field_name),
            actual=ai_pack_facts.get(field_name),
            missing_message="report or AI pack breakdown unavailable",
        ),
    ]


def _compare_check(
    *,
    name: str,
    expected: Any,
    actual: Any,
    missing_message: str,
) -> dict[str, Any]:
    if expected is None or actual is None:
        return MeshContextStructuralCheck(
            name=name,
            status="skipped",
            expected=expected,
            actual=actual,
            message=missing_message,
        ).to_dict()

    comparable_expected = _normalize_comparable_value(expected)
    comparable_actual = _normalize_comparable_value(actual)
    if comparable_expected == comparable_actual:
        return MeshContextStructuralCheck(
            name=name,
            status="passed",
            expected=expected,
            actual=actual,
            message="values match",
        ).to_dict()
    return MeshContextStructuralCheck(
        name=name,
        status="failed",
        expected=expected,
        actual=actual,
        message="values differ",
    ).to_dict()


def _normalize_comparable_value(value: Any) -> Any:
    """Normalize semantically equivalent structural facts for comparison.

    MeshContext Report may include closed-category zero entries such as
    ``function: 0`` while a raw graph payload breakdown often omits categories
    that are absent.  For structural validation, absent and zero-count category
    entries are equivalent.
    """

    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            if isinstance(item, bool):
                normalized[str(key)] = item
                continue
            if isinstance(item, int) and item == 0:
                continue
            if isinstance(item, float) and item == 0.0:
                continue
            normalized[str(key)] = _normalize_comparable_value(item)
        return _sort_mapping(normalized)
    if isinstance(value, list):
        return [_normalize_comparable_value(item) for item in value]
    return value


def _llm_guardrail_checks(
    report: Any,
    ai_pack: Any,
    benchmark: Any,
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    if report is not None:
        checks.append(
            _expect_false_check(
                name="mesh_context_report_contains_no_llm_inference",
                actual=_first_value(report, ("provenance.contains_llm_inference",), None),
            )
        )
    if ai_pack is not None:
        checks.append(
            _expect_false_check(
                name="ai_context_pack_contains_no_llm_inference",
                actual=_first_value(ai_pack, ("guardrails.contains_llm_inference",), None),
            )
        )
    if benchmark is not None:
        checks.append(
            _expect_false_check(
                name="token_benchmark_contains_no_llm_inference",
                actual=_first_value(benchmark, ("guardrails.contains_llm_inference",), None),
            )
        )
    return checks


def _expect_false_check(name: str, actual: Any) -> dict[str, Any]:
    if actual is None:
        return MeshContextStructuralCheck(
            name=name,
            status="skipped",
            expected=False,
            actual=None,
            message="guardrail field unavailable",
        ).to_dict()
    if actual is False:
        return MeshContextStructuralCheck(
            name=name,
            status="passed",
            expected=False,
            actual=actual,
            message="LLM inference is not present",
        ).to_dict()
    return MeshContextStructuralCheck(
        name=name,
        status="failed",
        expected=False,
        actual=actual,
        message="payload reports LLM inference presence",
    ).to_dict()


def _token_benchmark_calibration_checks(token_benchmark_facts: Mapping[str, Any]) -> list[dict[str, Any]]:
    if not token_benchmark_facts:
        return []
    baselines = token_benchmark_facts.get("source_baselines")
    profiles = token_benchmark_facts.get("profiles")
    notes = token_benchmark_facts.get("calibration_notes")
    return [
        _presence_check(
            name="token_benchmark_has_source_baselines",
            actual=baselines,
            expected_type=dict,
        ),
        _presence_check(
            name="token_benchmark_has_profile_metrics",
            actual=profiles,
            expected_type=dict,
        ),
        _presence_check(
            name="token_benchmark_has_calibration_notes",
            actual=notes,
            expected_type=list,
        ),
    ]


def _presence_check(name: str, actual: Any, expected_type: type) -> dict[str, Any]:
    if isinstance(actual, expected_type) and bool(actual):
        return MeshContextStructuralCheck(
            name=name,
            status="passed",
            expected=expected_type.__name__,
            actual=type(actual).__name__,
            message="required structure is present",
        ).to_dict()
    return MeshContextStructuralCheck(
        name=name,
        status="failed",
        expected=expected_type.__name__,
        actual=type(actual).__name__,
        message="required structure is missing or empty",
    ).to_dict()


def _extract_graph_payload_facts(payload: Mapping[str, Any]) -> dict[str, Any]:
    nodes = _extract_collection(payload, ("nodes", "nodes_by_uuid", "graph.nodes", "graph.nodes_by_uuid"))
    edges = _extract_collection(payload, ("edges", "edges_by_uuid", "graph.edges", "graph.edges_by_uuid"))
    node_count = _first_int(
        payload,
        ("node_count", "nodes_count", "stats.nodes", "stats.node_count", "graph.node_count"),
        default=len(nodes),
    )
    edge_count = _first_int(
        payload,
        ("edge_count", "edges_count", "stats.edges", "stats.edge_count", "graph.edge_count"),
        default=len(edges),
    )
    return _sort_mapping(
        {
            "node_count": node_count,
            "edge_count": edge_count,
            "node_type_breakdown": _extract_or_compute_breakdown(
                payload,
                ("node_type_breakdown", "stats.node_type_breakdown", "graph.node_type_breakdown"),
                nodes,
                ("type", "node_type", "kind", "category", "identity.type"),
            ),
            "edge_type_breakdown": _extract_or_compute_breakdown(
                payload,
                ("edge_type_breakdown", "stats.edge_type_breakdown", "graph.edge_type_breakdown"),
                edges,
                ("type", "edge_type", "kind", "relation", "relationship", "identity.type"),
            ),
        }
    )


def _extract_report_facts(payload: Mapping[str, Any]) -> dict[str, Any]:
    return _sort_mapping(
        {
            "node_count": _first_int(
                payload,
                ("graph_facts.node_count", "summary.node_count", "node_count"),
                default=0,
            ),
            "edge_count": _first_int(
                payload,
                ("graph_facts.edge_count", "summary.edge_count", "edge_count"),
                default=0,
            ),
            "node_type_breakdown": _first_mapping(
                payload,
                ("graph_facts.node_type_breakdown", "summary.node_type_breakdown", "node_type_breakdown"),
            ),
            "edge_type_breakdown": _first_mapping(
                payload,
                ("graph_facts.edge_type_breakdown", "summary.edge_type_breakdown", "edge_type_breakdown"),
            ),
        }
    )


def _extract_ai_pack_facts(payload: Mapping[str, Any]) -> dict[str, Any]:
    return _sort_mapping(
        {
            "node_count": _first_int(payload, ("executive_context.node_count",), default=0),
            "edge_count": _first_int(payload, ("executive_context.edge_count",), default=0),
            "node_type_breakdown": _first_mapping(payload, ("executive_context.node_type_breakdown",)),
            "edge_type_breakdown": _first_mapping(payload, ("executive_context.edge_type_breakdown",)),
        }
    )


def _extract_token_benchmark_facts(payload: Mapping[str, Any]) -> dict[str, Any]:
    return _sort_mapping(
        {
            "schema_version": payload.get("schema_version", _UNKNOWN),
            "benchmark_source_kind": payload.get("benchmark_source_kind", _UNKNOWN),
            "source_report_tokens": _first_int(payload, ("source_report_tokens",), default=0),
            "source_report_json_chars": _first_int(payload, ("source_report_json_chars",), default=0),
            "source_baselines": _first_mapping(payload, ("source_baselines",)),
            "profiles": _first_mapping(payload, ("profiles",)),
            "calibration_notes": _safe_list(payload.get("calibration_notes", [])),
        }
    )


def _extract_or_compute_breakdown(
    payload: Mapping[str, Any],
    explicit_paths: Sequence[str],
    records: Sequence[Any],
    type_paths: Sequence[str],
) -> dict[str, int]:
    explicit = _first_mapping(payload, explicit_paths)
    if explicit:
        return _normalize_int_mapping(explicit)

    counts: dict[str, int] = {}
    for record in records:
        if not isinstance(record, Mapping):
            continue
        label = None
        for path in type_paths:
            value = _get_path(record, path)
            if isinstance(value, str) and value:
                label = _safe_scalar(value)
                break
        if not label:
            label = _UNKNOWN
        counts[str(label)] = counts.get(str(label), 0) + 1
    return _sort_mapping(counts)


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


def _first_value(payload: Any, paths: Sequence[str], default: Any = None) -> Any:
    for path in paths:
        value = _get_path(payload, path)
        if value is not None:
            return value
    return default


def _first_int(payload: Any, paths: Sequence[str], default: int = 0) -> int:
    for path in paths:
        value = _get_path(payload, path)
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return max(value, 0)
        if isinstance(value, float) and value.is_integer():
            return max(int(value), 0)
    return max(int(default), 0)


def _first_mapping(payload: Any, paths: Sequence[str]) -> dict[str, Any]:
    for path in paths:
        value = _get_path(payload, path)
        if isinstance(value, Mapping):
            return _sort_mapping(_sanitize_value(dict(value)))
    return {}


def _get_path(payload: Any, path: str, default: Any = None) -> Any:
    current = payload
    for part in path.split("."):
        if isinstance(current, Mapping) and part in current:
            current = current[part]
        else:
            return default
    return current


def _safe_list(value: Any) -> list[Any]:
    plain = _to_plain(value)
    if not isinstance(plain, (list, tuple)):
        return []
    return [_sanitize_value(item) for item in plain]


def _safe_scalar(value: Any) -> str:
    text = str(value)
    if _is_unsafe_path_string(text):
        return _REDACTED
    return text


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
