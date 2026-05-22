"""MeshContext AI Context Pack token benchmark v0.1 helpers.

This module provides deterministic, side-effect free benchmark utilities for
comparing MeshContext Report payload size against MeshContext AI Context Pack
profiles.  The estimates intentionally use the same deterministic character
heuristic as the AI Context Pack contract; they are stable relative comparison
signals, not model-specific billing claims.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field, is_dataclass
import json
from typing import Any

from .mesh_context_ai_pack import (
    MESH_CONTEXT_AI_PACK_TOKEN_ESTIMATOR,
    SUPPORTED_MESH_CONTEXT_AI_PACK_PROFILES,
    build_mesh_context_ai_pack,
    estimate_mesh_context_tokens,
    find_unsafe_ai_pack_strings,
)


MESH_CONTEXT_TOKEN_BENCHMARK_SCHEMA_VERSION = "mesh_context_token_benchmark.v0.1"
MESH_CONTEXT_TOKEN_BENCHMARK_DIFF_SCHEMA_VERSION = "mesh_context_token_benchmark_diff.v0.1"


@dataclass(frozen=True)
class MeshContextTokenProfileBenchmark:
    """Deterministic token metrics for one AI Context Pack profile."""

    profile: str
    estimated_input_tokens: int
    estimated_source_report_tokens: int
    estimated_output_tokens: int
    estimated_json_chars: int
    estimated_token_reduction_percent: float
    token_ratio_to_source: float
    baseline_token_reduction_percent: dict[str, float]
    baseline_token_ratio_to_source: dict[str, float]
    included_hotspots_count: int
    total_hotspots_count: int
    hotspot_retention_percent: float
    included_risk_candidate_count: int
    total_risk_candidate_count: int
    risk_candidate_retention_percent: float
    included_evidence_node_count: int
    included_evidence_edge_count: int
    truncated_sections: list[str] = field(default_factory=list)
    omitted_sections: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MeshContextTokenBenchmark:
    """Top-level deterministic token benchmark contract."""

    schema_version: str
    estimator: str
    source_report_schema_version: str
    source_report_tokens: int
    source_report_json_chars: int
    benchmark_source_kind: str
    source_baselines: dict[str, dict[str, Any]]
    calibration_notes: list[str]
    profiles: dict[str, dict[str, Any]]
    best_profile_by_tokens: str | None
    max_token_reduction_percent: float
    guardrails: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_mesh_context_token_benchmark(
    report: Any,
    *,
    profiles: Sequence[str] | None = None,
    source_baselines: Mapping[str, Any] | None = None,
    benchmark_source_kind: str = "mesh_context_report",
) -> dict[str, Any]:
    """Build deterministic token benchmark metrics for AI Context Pack profiles.

    The function is pure: it performs no filesystem I/O, uses no network, and
    does not invoke an LLM.  It accepts partial synthetic fixtures as well as
    richer MeshContext Report payloads.
    """

    selected_profiles = _normalize_profiles(profiles)
    source_payload = _to_plain(report)
    source_tokens = estimate_mesh_context_tokens(source_payload)
    source_json_chars = _serialized_json_chars(source_payload)
    baseline_metrics = _build_source_baselines(
        source_payload,
        source_baselines=source_baselines,
    )

    profile_metrics: dict[str, dict[str, Any]] = {}
    packs: dict[str, dict[str, Any]] = {}
    for profile in selected_profiles:
        pack = build_mesh_context_ai_pack(source_payload, profile=profile)
        packs[profile] = pack
        estimated_input_tokens = _int_path(
            pack,
            "context_budget.estimated_input_tokens",
            default=estimate_mesh_context_tokens(pack),
        )
        profile_metrics[profile] = MeshContextTokenProfileBenchmark(
            profile=profile,
            estimated_input_tokens=estimated_input_tokens,
            estimated_source_report_tokens=_int_path(
                pack,
                "context_budget.estimated_source_report_tokens",
                default=source_tokens,
            ),
            estimated_output_tokens=_int_path(
                pack,
                "context_budget.estimated_output_tokens",
                default=0,
            ),
            estimated_json_chars=_serialized_json_chars(pack),
            estimated_token_reduction_percent=_float_path(
                pack,
                "context_budget.estimated_token_reduction_percent",
                default=_token_reduction_percent(
                    source_tokens,
                    estimate_mesh_context_tokens(pack),
                ),
            ),
            token_ratio_to_source=_token_ratio(
                estimated_input_tokens,
                source_tokens,
            ),
            baseline_token_reduction_percent=_baseline_reduction_map(
                baseline_metrics,
                estimated_input_tokens,
            ),
            baseline_token_ratio_to_source=_baseline_ratio_map(
                baseline_metrics,
                estimated_input_tokens,
            ),
            included_hotspots_count=_int_path(pack, "hotspot_context.included_count"),
            total_hotspots_count=_int_path(pack, "hotspot_context.total_count"),
            hotspot_retention_percent=_retention_percent(
                _int_path(pack, "hotspot_context.included_count"),
                _int_path(pack, "hotspot_context.total_count"),
            ),
            included_risk_candidate_count=_int_path(pack, "risk_context.included_count"),
            total_risk_candidate_count=_int_path(pack, "risk_context.total_count"),
            risk_candidate_retention_percent=_retention_percent(
                _int_path(pack, "risk_context.included_count"),
                _int_path(pack, "risk_context.total_count"),
            ),
            included_evidence_node_count=len(_mapping_path(pack, "evidence_index.nodes")),
            included_evidence_edge_count=len(_mapping_path(pack, "evidence_index.edges")),
            truncated_sections=_string_list_path(pack, "omissions.truncated_sections"),
            omitted_sections=_string_list_path(pack, "omissions.omitted_sections"),
        ).to_dict()

    best_profile = _best_profile_by_tokens(profile_metrics)
    max_reduction = max(
        (float(item.get("estimated_token_reduction_percent", 0.0)) for item in profile_metrics.values()),
        default=0.0,
    )

    benchmark = MeshContextTokenBenchmark(
        schema_version=MESH_CONTEXT_TOKEN_BENCHMARK_SCHEMA_VERSION,
        estimator=MESH_CONTEXT_AI_PACK_TOKEN_ESTIMATOR,
        source_report_schema_version=str(
            _first_value(
                source_payload,
                ("schema_version", "report_schema_version", "mesh_context_report_schema_version"),
                "unknown",
            )
        ),
        source_report_tokens=source_tokens,
        source_report_json_chars=source_json_chars,
        benchmark_source_kind=str(benchmark_source_kind),
        source_baselines=_sort_mapping(baseline_metrics),
        calibration_notes=_build_calibration_notes(
            baseline_metrics,
            benchmark_source_kind=str(benchmark_source_kind),
        ),
        profiles=_sort_mapping(profile_metrics),
        best_profile_by_tokens=best_profile,
        max_token_reduction_percent=round(max_reduction, 2),
        guardrails={
            "contains_llm_inference": False,
            "deterministic_estimates_only": True,
            "filesystem_io_not_performed": True,
            "model_specific_tokenizer_not_used": True,
            "raw_payloads_not_embedded": True,
        },
    ).to_dict()

    # The benchmark intentionally does not embed the source report or full packs.
    # It contains only deterministic metrics derived from them.
    return _sort_mapping(_to_plain(benchmark))


def compare_mesh_context_token_benchmarks(before: Any, after: Any) -> dict[str, Any]:
    """Compare two token benchmark payloads with stable delta fields."""

    before_payload = _to_plain(before)
    after_payload = _to_plain(after)
    before_profiles = _mapping_path(before_payload, "profiles")
    after_profiles = _mapping_path(after_payload, "profiles")
    profile_names = sorted(set(before_profiles) | set(after_profiles), key=str)

    profile_deltas: dict[str, dict[str, Any]] = {}
    for profile in profile_names:
        before_profile = before_profiles.get(profile, {})
        after_profile = after_profiles.get(profile, {})
        if not isinstance(before_profile, Mapping):
            before_profile = {}
        if not isinstance(after_profile, Mapping):
            after_profile = {}
        profile_deltas[str(profile)] = _sort_mapping(
            {
                "estimated_input_tokens_delta": _int_value(after_profile.get("estimated_input_tokens"))
                - _int_value(before_profile.get("estimated_input_tokens")),
                "estimated_token_reduction_percent_delta": round(
                    _float_value(after_profile.get("estimated_token_reduction_percent"))
                    - _float_value(before_profile.get("estimated_token_reduction_percent")),
                    2,
                ),
                "hotspot_retention_percent_delta": round(
                    _float_value(after_profile.get("hotspot_retention_percent"))
                    - _float_value(before_profile.get("hotspot_retention_percent")),
                    2,
                ),
                "risk_candidate_retention_percent_delta": round(
                    _float_value(after_profile.get("risk_candidate_retention_percent"))
                    - _float_value(before_profile.get("risk_candidate_retention_percent")),
                    2,
                ),
            }
        )

    return _sort_mapping(
        {
            "schema_version": MESH_CONTEXT_TOKEN_BENCHMARK_DIFF_SCHEMA_VERSION,
            "before_schema_version": before_payload.get("schema_version", "unknown")
            if isinstance(before_payload, Mapping)
            else "unknown",
            "after_schema_version": after_payload.get("schema_version", "unknown")
            if isinstance(after_payload, Mapping)
            else "unknown",
            "source_report_tokens_delta": _int_path(after_payload, "source_report_tokens")
            - _int_path(before_payload, "source_report_tokens"),
            "source_report_json_chars_delta": _int_path(after_payload, "source_report_json_chars")
            - _int_path(before_payload, "source_report_json_chars"),
            "best_profile_changed": _first_value(before_payload, ("best_profile_by_tokens",), None)
            != _first_value(after_payload, ("best_profile_by_tokens",), None),
            "profiles": profile_deltas,
        }
    )


def find_unsafe_token_benchmark_strings(payload: Any) -> list[str]:
    """Return unsafe strings from benchmark-like payloads.

    Reuses the AI pack privacy scanner to keep path safety behavior aligned
    across semantic contracts.
    """

    return find_unsafe_ai_pack_strings(payload)



def _build_source_baselines(
    source_payload: Any,
    *,
    source_baselines: Mapping[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    """Build deterministic source baseline metrics without embedding payloads."""

    baselines: dict[str, dict[str, Any]] = {
        "mesh_context_report": _source_baseline_metrics(source_payload),
    }
    if source_baselines:
        for raw_name, raw_payload in sorted(source_baselines.items(), key=lambda pair: str(pair[0])):
            name = str(raw_name).strip() or "unnamed_source_baseline"
            if name == "mesh_context_report":
                # The primary report baseline is derived from the report argument.
                continue
            baselines[name] = _source_baseline_metrics(raw_payload)
    return _sort_mapping(baselines)


def _source_baseline_metrics(payload: Any) -> dict[str, Any]:
    """Return token/size metrics only; never embed the raw source payload."""

    plain = _to_plain(payload)
    if isinstance(plain, Mapping) and (
        "estimated_tokens" in plain or "json_chars" in plain
    ):
        estimated_tokens = _int_value(plain.get("estimated_tokens"))
        json_chars = _int_value(plain.get("json_chars"))
        if estimated_tokens <= 0:
            estimated_tokens = estimate_mesh_context_tokens(plain.get("payload", plain))
        if json_chars <= 0:
            json_chars = _serialized_json_chars(plain.get("payload", plain))
    else:
        estimated_tokens = estimate_mesh_context_tokens(plain)
        json_chars = _serialized_json_chars(plain)

    return _sort_mapping(
        {
            "estimated_tokens": max(estimated_tokens, 0),
            "json_chars": max(json_chars, 0),
            "embeds_raw_payload": False,
        }
    )


def _baseline_reduction_map(
    baseline_metrics: Mapping[str, Any],
    pack_tokens: int,
) -> dict[str, float]:
    result: dict[str, float] = {}
    for name, metrics in baseline_metrics.items():
        source_tokens = _int_path(metrics, "estimated_tokens")
        result[str(name)] = _token_reduction_percent(source_tokens, pack_tokens)
    return _sort_mapping(result)


def _baseline_ratio_map(
    baseline_metrics: Mapping[str, Any],
    pack_tokens: int,
) -> dict[str, float]:
    result: dict[str, float] = {}
    for name, metrics in baseline_metrics.items():
        source_tokens = _int_path(metrics, "estimated_tokens")
        result[str(name)] = _token_ratio(pack_tokens, source_tokens)
    return _sort_mapping(result)


def _build_calibration_notes(
    baseline_metrics: Mapping[str, Any],
    *,
    benchmark_source_kind: str,
) -> list[str]:
    notes = [
        "Token estimates use a deterministic character heuristic and are not model-specific billing claims.",
        "Benchmarks contain derived metrics only and do not embed raw reports, graph payloads, or AI Context Packs.",
    ]
    if benchmark_source_kind == "mesh_context_report":
        notes.append(
            "Negative reduction can occur when the MeshContext Report baseline is already a minimal MCP projection."
        )
    if "serialized_graph_payload" in baseline_metrics:
        notes.append(
            "serialized_graph_payload baseline measures the MCP graph snapshot serialization size without exposing the raw payload."
        )
    return sorted(set(notes))


def _normalize_profiles(profiles: Sequence[str] | None) -> tuple[str, ...]:
    if profiles is None:
        return tuple(SUPPORTED_MESH_CONTEXT_AI_PACK_PROFILES)
    result: list[str] = []
    for profile in profiles:
        if profile not in SUPPORTED_MESH_CONTEXT_AI_PACK_PROFILES:
            supported = ", ".join(SUPPORTED_MESH_CONTEXT_AI_PACK_PROFILES)
            raise ValueError(f"Unsupported MeshContext AI pack profile: {profile!r}. Supported: {supported}")
        if profile not in result:
            result.append(str(profile))
    return tuple(result)


def _best_profile_by_tokens(profile_metrics: Mapping[str, Any]) -> str | None:
    if not profile_metrics:
        return None
    return min(
        (str(profile) for profile in profile_metrics),
        key=lambda profile: (
            _int_path(profile_metrics[profile], "estimated_input_tokens"),
            profile,
        ),
    )


def _serialized_json_chars(payload: Any) -> int:
    return len(
        json.dumps(
            _to_plain(payload),
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
    )


def _token_reduction_percent(source_tokens: int, pack_tokens: int) -> float:
    if source_tokens <= 0:
        return 0.0
    return round(max(-100.0, min(100.0, ((source_tokens - pack_tokens) / source_tokens) * 100.0)), 2)


def _token_ratio(pack_tokens: int, source_tokens: int) -> float:
    if source_tokens <= 0:
        return 0.0
    return round(pack_tokens / source_tokens, 4)


def _retention_percent(included: int, total: int) -> float:
    if total <= 0:
        return 100.0
    return round((max(included, 0) / total) * 100.0, 2)


def _string_list_path(payload: Any, path: str) -> list[str]:
    value = _get_path(payload, path, default=[])
    if not isinstance(value, list):
        return []
    return sorted(str(item) for item in value if isinstance(item, str))


def _mapping_path(payload: Any, path: str) -> dict[str, Any]:
    value = _get_path(payload, path, default={})
    if isinstance(value, Mapping):
        return {str(key): item for key, item in value.items()}
    return {}


def _int_path(payload: Any, path: str, default: int = 0) -> int:
    return _int_value(_get_path(payload, path, default=default), default=default)


def _float_path(payload: Any, path: str, default: float = 0.0) -> float:
    return _float_value(_get_path(payload, path, default=default), default=default)


def _int_value(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return default


def _float_value(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    return default


def _first_value(payload: Any, paths: Sequence[str], default: Any = None) -> Any:
    for path in paths:
        value = _get_path(payload, path, default=None)
        if value is not None:
            return value
    return default


def _get_path(payload: Any, path: str, default: Any = None) -> Any:
    current = payload
    for part in path.split("."):
        if isinstance(current, Mapping) and part in current:
            current = current[part]
            continue
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
