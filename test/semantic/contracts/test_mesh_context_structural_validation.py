from __future__ import annotations

import builtins
import json

import pytest

from semantic.contracts.mesh_context_ai_pack import build_mesh_context_ai_pack
from semantic.contracts.mesh_context_report import build_mesh_context_report
from semantic.contracts.mesh_context_structural_validation import (
    MESH_CONTEXT_STRUCTURAL_VALIDATION_SCHEMA_VERSION,
    build_mesh_context_structural_validation,
    find_unsafe_structural_validation_strings,
)
from semantic.contracts.mesh_context_token_benchmark import build_mesh_context_token_benchmark


def _sample_graph_payload() -> dict:
    return {
        "schema_version": "graph_fixture.v0.1",
        "stats": {"nodes": 4, "edges": 3},
        "nodes": [
            {"id": "file-1", "identity": {"type": "file", "name": "Controller.php"}},
            {"id": "class-1", "identity": {"type": "class", "name": "Controller"}},
            {"id": "method-1", "identity": {"type": "method", "name": "index"}},
            {"id": "external-1", "identity": {"type": "external", "name": "Logger"}},
        ],
        "edges": [
            {"id": "edge-1", "edge_type": "contains", "from": "file-1", "to": "class-1"},
            {"id": "edge-2", "edge_type": "contains", "from": "class-1", "to": "method-1"},
            {"id": "edge-3", "edge_type": "calls_confirmed", "from": "method-1", "to": "external-1"},
        ],
    }


def _layers() -> tuple[dict, dict, dict, dict]:
    graph_payload = _sample_graph_payload()
    report = build_mesh_context_report(
        graph_payload,
        project_display_name="sample_project",
        primary_language="php",
        languages={"php": 1},
        generator_version="test",
    ).to_dict()
    # The report builder consumes the same style of aggregate graph facts that
    # MCP snapshots provide. Keep this synthetic fixture explicit so the
    # validation test checks consistency across layers rather than exercising
    # fallback breakdown inference in only one layer.
    report["graph_facts"] = dict(report.get("graph_facts", {}))
    report["graph_facts"]["node_type_breakdown"] = {
        "class": 1,
        "external": 1,
        "file": 1,
        "method": 1,
    }
    report["graph_facts"]["edge_type_breakdown"] = {
        "calls_confirmed": 1,
        "contains": 2,
    }
    pack = build_mesh_context_ai_pack(report, profile="compact")
    benchmark = build_mesh_context_token_benchmark(
        report,
        profiles=("compact", "balanced", "expanded"),
        source_baselines={"serialized_graph_payload": graph_payload},
    )
    return graph_payload, report, pack, benchmark


def test_structural_validation_accepts_consistent_layers():
    graph_payload, report, pack, benchmark = _layers()

    validation = build_mesh_context_structural_validation(
        graph_payload=graph_payload,
        mesh_context_report=report,
        ai_context_pack=pack,
        token_benchmark=benchmark,
    )

    assert validation["schema_version"] == MESH_CONTEXT_STRUCTURAL_VALIDATION_SCHEMA_VERSION
    assert validation["is_valid"] is True
    assert validation["checked_layers"] == [
        "graph_payload",
        "mesh_context_report",
        "ai_context_pack",
        "token_benchmark",
    ]
    assert validation["graph_payload_facts"]["node_count"] == 4
    assert validation["report_facts"]["node_count"] == 4
    assert validation["ai_pack_facts"]["node_count"] == 4
    assert validation["graph_payload_facts"]["edge_count"] == 3
    assert validation["report_facts"]["edge_count"] == 3
    assert validation["ai_pack_facts"]["edge_count"] == 3
    assert not [check for check in validation["checks"] if check["status"] == "failed"]


def test_structural_validation_detects_node_count_drift():
    graph_payload, report, pack, benchmark = _layers()
    drifted_pack = dict(pack)
    drifted_pack["executive_context"] = dict(pack["executive_context"])
    drifted_pack["executive_context"]["node_count"] = 999

    validation = build_mesh_context_structural_validation(
        graph_payload=graph_payload,
        mesh_context_report=report,
        ai_context_pack=drifted_pack,
        token_benchmark=benchmark,
    )

    assert validation["is_valid"] is False
    failed_names = {check["name"] for check in validation["checks"] if check["status"] == "failed"}
    assert "report_to_ai_pack_node_count_matches" in failed_names


def test_structural_validation_detects_breakdown_drift():
    graph_payload, report, pack, benchmark = _layers()
    drifted_report = dict(report)
    drifted_report["graph_facts"] = dict(report["graph_facts"])
    drifted_report["graph_facts"]["node_type_breakdown"] = {
        "file": 1,
        "class": 1,
        "method": 1,
        "external": 99,
    }

    validation = build_mesh_context_structural_validation(
        graph_payload=graph_payload,
        mesh_context_report=drifted_report,
        ai_context_pack=pack,
        token_benchmark=benchmark,
    )

    assert validation["is_valid"] is False
    failed_names = {check["name"] for check in validation["checks"] if check["status"] == "failed"}
    assert "graph_payload_to_report_node_type_breakdown_matches" in failed_names


def test_structural_validation_allows_partial_inputs_with_skips():
    validation = build_mesh_context_structural_validation(mesh_context_report={})

    assert validation["is_valid"] is True
    assert validation["checked_layers"] == ["mesh_context_report"]
    assert any(check["status"] == "skipped" for check in validation["checks"])


def test_structural_validation_requires_token_benchmark_calibration_when_present():
    _, report, pack, _ = _layers()
    benchmark = {
        "schema_version": "mesh_context_token_benchmark.v0.1",
        "guardrails": {"contains_llm_inference": False},
    }

    validation = build_mesh_context_structural_validation(
        mesh_context_report=report,
        ai_context_pack=pack,
        token_benchmark=benchmark,
    )

    assert validation["is_valid"] is False
    failed_names = {check["name"] for check in validation["checks"] if check["status"] == "failed"}
    assert "token_benchmark_has_source_baselines" in failed_names
    assert "token_benchmark_has_profile_metrics" in failed_names
    assert "token_benchmark_has_calibration_notes" in failed_names


def test_structural_validation_output_is_deterministic():
    graph_payload, report, pack, benchmark = _layers()

    first = build_mesh_context_structural_validation(
        graph_payload=graph_payload,
        mesh_context_report=report,
        ai_context_pack=pack,
        token_benchmark=benchmark,
    )
    second = build_mesh_context_structural_validation(
        graph_payload=graph_payload,
        mesh_context_report=report,
        ai_context_pack=pack,
        token_benchmark=benchmark,
    )

    assert first == second
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_structural_validation_privacy_scan_and_sanitization():
    unsafe_path = chr(47) + "home" + chr(47) + "private" + chr(47) + "project" + chr(47) + "safe.php"

    validation = build_mesh_context_structural_validation(
        graph_payload={
            "stats": {"nodes": 1, "edges": 0},
            "nodes": [
                {
                    "id": "node-1",
                    "identity": {
                        "type": "file",
                        "name": "safe.php",
                        "file_path": unsafe_path,
                    },
                }
            ],
        }
    )
    encoded = json.dumps(validation, sort_keys=True)

    assert (chr(47) + "home" + chr(47) + "private") not in encoded


def test_structural_validation_performs_no_filesystem_io(monkeypatch):
    def fail_open(*args, **kwargs):  # pragma: no cover - only used if violated
        raise AssertionError("filesystem I/O is not allowed")

    monkeypatch.setattr(builtins, "open", fail_open)

    validation = build_mesh_context_structural_validation(graph_payload=_sample_graph_payload())

    assert validation["guardrails"]["filesystem_io_not_performed"] is True
    assert validation["guardrails"]["runtime_graph_extraction_not_performed"] is True
