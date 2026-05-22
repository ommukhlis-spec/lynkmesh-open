import json

import pytest

from lynkmesh.semantic.contracts import (
    MESH_CONTEXT_REPORT_TYPE,
    MESH_CONTEXT_SCHEMA_VERSION,
    MeshContextReport,
    build_mesh_context_report,
    find_unsafe_report_strings,
)


def _payload():
    return {
        "schema_version": "3.1.0",
        "version": {
            "metadata": {
                "graph_id": "graph-1",
                "build_id": "build-1",
                "git_commit": "abc123",
            },
            "content_hash": "f" * 64,
        },
        "stats": {
            "nodes": 7,
            "edges": 3,
            "files": 2,
            "classes": 1,
            "methods": 2,
            "functions": 1,
            "external": 1,
        },
        "nodes": [
            {"uuid": "n1", "identity": "file-a"},
            {"uuid": "n2", "identity": "class-a"},
        ],
        "edges": [
            {"uuid": "e1", "source_uuid": "n1", "target_uuid": "n2", "type": "contains", "confidence": "EXACT"},
            {"uuid": "e2", "source_uuid": "n2", "target_uuid": "n3", "type": "calls", "confidence": "HEURISTIC"},
            {"uuid": "e3", "source_uuid": "n2", "target_uuid": "n4", "type": "calls", "confidence": "unexpected"},
        ],
    }


def test_schema_version_constant():
    assert MESH_CONTEXT_SCHEMA_VERSION == "0.1.0"


def test_report_type_constant():
    assert MESH_CONTEXT_REPORT_TYPE == "mesh_context_report"


def test_top_level_keys_are_frozen():
    report = build_mesh_context_report(
        _payload(),
        project_display_name="demo-project",
        primary_language="php",
        languages={"php": 2},
        pipeline_schema_version="3.4.0",
        parser_source="internal_bundle",
        parser_executor_mode="thread",
        generated_at="2026-01-01T00:00:00+00:00",
    )

    assert set(report.to_dict()) == {
        "schema_version",
        "report_type",
        "generated_at",
        "project",
        "build",
        "graph_facts",
        "languages",
        "entrypoints",
        "hotspots",
        "risk_candidates",
        "dependency_summary",
        "limitations",
        "llm_instructions",
        "provenance",
    }


def test_build_projection_from_serialized_payload():
    report = build_mesh_context_report(
        _payload(),
        project_display_name="demo-project",
        primary_language="php",
        languages={"php": 2},
        pipeline_schema_version="3.4.0",
        parser_source="internal_bundle",
        parser_executor_mode="thread",
        generated_at="2026-01-01T00:00:00+00:00",
    )
    data = report.to_dict()

    assert data["schema_version"] == MESH_CONTEXT_SCHEMA_VERSION
    assert data["report_type"] == MESH_CONTEXT_REPORT_TYPE
    assert data["project"]["display_name"] == "demo-project"
    assert data["project"]["primary_language"] == "php"
    assert data["build"]["build_id"] == "build-1"
    assert data["build"]["graph_id"] == "graph-1"
    assert data["build"]["content_hash"] == "f" * 64
    assert data["build"]["serializer_schema_version"] == "3.1.0"
    assert data["build"]["pipeline_schema_version"] == "3.4.0"
    assert data["build"]["parser_source"] == "internal_bundle"
    assert data["build"]["parser_executor_mode"] == "thread"


def test_graph_facts_are_projected():
    report = build_mesh_context_report(_payload(), languages={"php": 2})
    facts = report.to_dict()["graph_facts"]

    assert facts["node_count"] == 7
    assert facts["edge_count"] == 3
    assert facts["node_type_breakdown"] == {
        "file": 2,
        "class": 1,
        "method": 2,
        "function": 1,
        "external": 1,
    }
    assert facts["edge_type_breakdown"] == {
        "calls": 2,
        "contains": 1,
    }
    assert facts["confidence_distribution"]["EXACT"] == 1
    assert facts["confidence_distribution"]["HEURISTIC"] == 1
    assert facts["confidence_distribution"]["UNKNOWN"] == 1


def test_provenance_declares_no_llm_inference():
    report = build_mesh_context_report(_payload(), generator_version="4.3.1")
    provenance = report.to_dict()["provenance"]

    assert provenance["generator"] == "lynkmesh"
    assert provenance["generator_version"] == "4.3.1"
    assert provenance["graph_content_hash"] == "f" * 64
    assert provenance["is_deterministic"] is True
    assert provenance["contains_llm_inference"] is False


def test_candidate_sections_start_empty_in_v0_1():
    report = build_mesh_context_report(_payload())
    data = report.to_dict()

    assert data["entrypoints"] == []
    assert data["hotspots"] == []
    assert data["risk_candidates"] == []
    assert data["dependency_summary"]["cycles_detected"] == 0


def test_json_round_trip():
    report = build_mesh_context_report(
        _payload(),
        generated_at="2026-01-01T00:00:00+00:00",
    )
    encoded = json.dumps(report.to_dict(), sort_keys=True)
    decoded = json.loads(encoded)

    assert decoded == report.to_dict()


def test_deterministic_sections_ignore_generated_at():
    a = build_mesh_context_report(
        _payload(),
        generated_at="2026-01-01T00:00:00+00:00",
    )
    b = build_mesh_context_report(
        _payload(),
        generated_at="2026-01-02T00:00:00+00:00",
    )

    assert a.generated_at != b.generated_at
    assert a.deterministic_sections() == b.deterministic_sections()


def test_write_report(tmp_path):
    report = build_mesh_context_report(
        _payload(),
        generated_at="2026-01-01T00:00:00+00:00",
    )
    out = tmp_path / "mesh_context_report.json"

    report.write(out)

    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert loaded["schema_version"] == MESH_CONTEXT_SCHEMA_VERSION
    assert loaded["provenance"]["contains_llm_inference"] is False


def test_minimal_payload_degrades_gracefully():
    report = build_mesh_context_report({})
    data = report.to_dict()

    assert data["build"]["content_hash"] == ""
    assert data["graph_facts"]["node_count"] == 0
    assert data["graph_facts"]["edge_count"] == 0
    assert data["languages"]["primary"] == "unknown"


def test_project_display_name_sanitizes_path_like_input():
    unsafe_path = "C:" + "\\" + "Users" + "\\" + "someone" + "\\" + "demo-project"
    report = build_mesh_context_report(
        _payload(),
        project_display_name=unsafe_path,
    )

    assert report.to_dict()["project"]["display_name"] == "demo-project"
    assert find_unsafe_report_strings(report.to_dict()) == []


def test_unsafe_string_detector_flags_path_like_values():
    unsafe_path = "C:" + "\\" + "Users" + "\\" + "someone" + "\\" + "demo-project"

    findings = find_unsafe_report_strings({"x": unsafe_path})

    assert findings


def test_build_rejects_unsanitized_unsafe_report_strings(monkeypatch):
    report = MeshContextReport()
    unsafe_path = "C:" + "\\" + "Users" + "\\" + "someone" + "\\" + "demo-project"

    monkeypatch.setattr(
        report,
        "limitations",
        [unsafe_path],
        raising=False,
    )

    assert find_unsafe_report_strings(report.to_dict())


def test_language_mix_is_sorted_and_normalized():
    report = build_mesh_context_report(
        _payload(),
        languages={"PHP": 2, "js": "3"},
    )

    assert report.to_dict()["languages"]["mix"] == {"js": 3, "php": 2}
    assert report.to_dict()["languages"]["supported"] == ["js", "php"]