import builtins

import pytest

from semantic.contracts.mesh_context_token_benchmark import (
    MESH_CONTEXT_TOKEN_BENCHMARK_DIFF_SCHEMA_VERSION,
    MESH_CONTEXT_TOKEN_BENCHMARK_SCHEMA_VERSION,
    build_mesh_context_token_benchmark,
    compare_mesh_context_token_benchmarks,
    find_unsafe_token_benchmark_strings,
)


def _sample_report(*, node_count=60, edge_count=80, hotspots=8, risks=7):
    nodes = {
        f"node-{index:03d}": {
            "id": f"node-{index:03d}",
            "type": "controller" if index % 3 == 0 else "service",
            "label": f"SampleComponent{index}",
            "confidence": "high",
        }
        for index in range(node_count)
    }
    edges = {
        f"edge-{index:03d}": {
            "id": f"edge-{index:03d}",
            "type": "calls" if index % 2 == 0 else "imports",
            "confidence": "medium",
        }
        for index in range(edge_count)
    }
    return {
        "schema_version": "0.1.0",
        "project": {
            "display_name": "sample_project",
            "language_hints": ["python"],
        },
        "graph_facts": {
            "node_count": node_count,
            "edge_count": edge_count,
            "nodes_by_uuid": nodes,
            "edges_by_uuid": edges,
            "node_type_breakdown": {"controller": node_count // 3, "service": node_count - (node_count // 3)},
            "edge_type_breakdown": {"calls": edge_count // 2, "imports": edge_count - (edge_count // 2)},
        },
        "hotspots": [
            {"id": f"hotspot-{index}", "label": f"Hotspot {index}", "evidence_ids": [f"node-{index:03d}"]}
            for index in range(hotspots)
        ],
        "risk_candidates": [
            {"id": f"risk-{index}", "label": f"Risk {index}", "evidence_ids": [f"node-{index:03d}"]}
            for index in range(risks)
        ],
        "dependency_summary": {
            "internal_dependency_count": 12,
            "external_dependency_count": 3,
            "important_internal_dependencies": [
                {"id": f"dep-{index}", "weight": index}
                for index in range(12)
            ],
        },
        "large_raw_context_fixture": [
            {"path_free_symbol": f"symbol_{index}", "notes": "x" * 80}
            for index in range(120)
        ],
    }


def test_token_benchmark_is_deterministic():
    report = _sample_report()

    first = build_mesh_context_token_benchmark(report)
    second = build_mesh_context_token_benchmark(report)

    assert first == second
    assert first["schema_version"] == MESH_CONTEXT_TOKEN_BENCHMARK_SCHEMA_VERSION
    assert first["estimator"] == "deterministic_char_heuristic_v0.1"


def test_token_benchmark_includes_all_profiles_by_default():
    benchmark = build_mesh_context_token_benchmark(_sample_report())

    assert list(benchmark["profiles"]) == ["balanced", "compact", "expanded"]
    assert benchmark["best_profile_by_tokens"] in {"compact", "balanced", "expanded"}
    assert benchmark["source_report_tokens"] > 0
    assert benchmark["source_report_json_chars"] > 0


def test_compact_profile_is_token_conscious_against_large_report_fixture():
    benchmark = build_mesh_context_token_benchmark(_sample_report())

    compact = benchmark["profiles"]["compact"]
    expanded = benchmark["profiles"]["expanded"]

    assert compact["estimated_input_tokens"] <= expanded["estimated_input_tokens"]
    assert compact["estimated_token_reduction_percent"] > 0
    assert compact["token_ratio_to_source"] < 1


def test_retention_metrics_are_reported_per_profile():
    benchmark = build_mesh_context_token_benchmark(_sample_report(hotspots=8, risks=7))
    compact = benchmark["profiles"]["compact"]
    balanced = benchmark["profiles"]["balanced"]

    assert compact["included_hotspots_count"] == 5
    assert compact["total_hotspots_count"] == 8
    assert compact["hotspot_retention_percent"] == 62.5
    assert compact["included_risk_candidate_count"] == 5
    assert compact["risk_candidate_retention_percent"] == pytest.approx(71.43)
    assert balanced["hotspot_retention_percent"] == 100.0
    assert balanced["risk_candidate_retention_percent"] == 100.0


def test_selected_profiles_can_be_limited_and_deduplicated():
    benchmark = build_mesh_context_token_benchmark(
        _sample_report(),
        profiles=("compact", "compact", "balanced"),
    )

    assert list(benchmark["profiles"]) == ["balanced", "compact"]


def test_unsupported_profile_is_rejected():
    with pytest.raises(ValueError):
        build_mesh_context_token_benchmark(_sample_report(), profiles=("tiny",))


def test_empty_report_still_has_stable_defaults():
    benchmark = build_mesh_context_token_benchmark({}, profiles=("compact",))
    compact = benchmark["profiles"]["compact"]

    assert benchmark["source_report_schema_version"] == "unknown"
    assert compact["total_hotspots_count"] == 0
    assert compact["hotspot_retention_percent"] == 100.0
    assert compact["total_risk_candidate_count"] == 0
    assert compact["risk_candidate_retention_percent"] == 100.0


def test_compare_token_benchmarks_reports_deltas():
    before = build_mesh_context_token_benchmark(_sample_report(node_count=10, edge_count=10), profiles=("compact",))
    after = build_mesh_context_token_benchmark(_sample_report(node_count=40, edge_count=50), profiles=("compact",))

    diff = compare_mesh_context_token_benchmarks(before, after)

    assert diff["schema_version"] == MESH_CONTEXT_TOKEN_BENCHMARK_DIFF_SCHEMA_VERSION
    assert diff["source_report_tokens_delta"] != 0
    assert "compact" in diff["profiles"]
    assert "estimated_input_tokens_delta" in diff["profiles"]["compact"]


def test_token_benchmark_does_not_embed_raw_report_or_packs():
    benchmark = build_mesh_context_token_benchmark(_sample_report(), profiles=("compact",))

    assert "large_raw_context_fixture" not in benchmark
    assert "ai_context_pack" not in benchmark
    assert "source_report" not in benchmark


def test_token_benchmark_privacy_scan_stays_clean():
    benchmark = build_mesh_context_token_benchmark(
        {
            "schema_version": "0.1.0",
            "project": {"display_name": "sample_project"},
            "nodes_by_uuid": {
                "node-1": {
                    "id": "node-1",
                    "label": "C:" + "/Users/local/project/file.py",
                    "type": "file",
                }
            },
        },
        profiles=("compact",),
    )

    assert find_unsafe_token_benchmark_strings(benchmark) == []




def test_token_benchmark_includes_calibrated_source_baselines():
    benchmark = build_mesh_context_token_benchmark(
        _sample_report(),
        profiles=("compact",),
        source_baselines={
            "serialized_graph_payload": {
                "nodes": [{"id": f"node-{index}", "type": "method"} for index in range(20)],
                "edges": [{"id": f"edge-{index}", "type": "calls"} for index in range(30)],
            }
        },
    )

    assert benchmark["benchmark_source_kind"] == "mesh_context_report"
    assert "calibration_notes" in benchmark
    assert "mesh_context_report" in benchmark["source_baselines"]
    assert "serialized_graph_payload" in benchmark["source_baselines"]
    assert benchmark["source_baselines"]["serialized_graph_payload"]["estimated_tokens"] > 0
    assert benchmark["source_baselines"]["serialized_graph_payload"]["embeds_raw_payload"] is False

    compact = benchmark["profiles"]["compact"]
    assert "serialized_graph_payload" in compact["baseline_token_reduction_percent"]
    assert "serialized_graph_payload" in compact["baseline_token_ratio_to_source"]


def test_token_benchmark_source_baselines_do_not_embed_raw_payloads():
    benchmark = build_mesh_context_token_benchmark(
        _sample_report(),
        profiles=("compact",),
        source_baselines={
            "serialized_graph_payload": {
                "private_path": "C:/Users/example/private/project",
                "payload": {"node_count": 100, "edge_count": 200},
            }
        },
    )

    encoded = str(benchmark)
    assert "C:/Users" not in encoded
    assert benchmark["guardrails"]["raw_payloads_not_embedded"] is True


def test_token_benchmark_performs_no_filesystem_io(monkeypatch):
    def fail_open(*args, **kwargs):
        raise AssertionError("unexpected filesystem access")

    monkeypatch.setattr(builtins, "open", fail_open)

    benchmark = build_mesh_context_token_benchmark(_sample_report(), profiles=("compact",))

    assert benchmark["guardrails"]["filesystem_io_not_performed"] is True
    assert benchmark["guardrails"]["contains_llm_inference"] is False
