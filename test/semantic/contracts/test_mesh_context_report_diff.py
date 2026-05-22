import builtins
import json

from semantic.contracts.mesh_context_diff import (
    build_mesh_context_benchmark_vector,
    build_mesh_context_report_diff,
    diff_mesh_context_benchmark_vectors,
)


def _sample_report():
    return {
        "graph_summary": {
            "node_count": 3,
            "edge_count": 2,
            "node_type_breakdown": {"class": 1, "function": 2},
            "edge_type_breakdown": {"calls": 2},
            "confidence_distribution": {"0.75-1.00": 2, "0.50-0.75": 1},
            "dependency_summary": {
                "internal_edges": 2,
                "external_edges": 0,
                "top_dependencies": ["Controller", "Service"],
            },
        },
        "hotspots": [{"id": "Controller"}],
        "risk_candidates": [{"id": "Repository"}, {"id": "Service"}],
    }


def test_benchmark_vector_extraction_is_deterministic():
    first = build_mesh_context_benchmark_vector(_sample_report())
    second = build_mesh_context_benchmark_vector(_sample_report())

    assert first == second
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_missing_optional_sections_produce_stable_defaults():
    vector = build_mesh_context_benchmark_vector({})

    assert vector["node_count"] == 0
    assert vector["edge_count"] == 0
    assert vector["node_type_breakdown"] == {}
    assert vector["edge_type_breakdown"] == {}
    assert vector["confidence_distribution"] == {}
    assert vector["hotspots_count"] == 0
    assert vector["risk_candidate_count"] == 0
    assert vector["dependency_summary"] == {}


def test_same_vector_produces_noop_diff():
    vector = build_mesh_context_benchmark_vector(_sample_report())
    diff = diff_mesh_context_benchmark_vectors(vector, vector)

    assert diff["changed"] is False
    assert diff["summary"]["added"] == 0
    assert diff["summary"]["removed"] == 0
    assert diff["summary"]["changed"] == 0
    assert diff["added"] == []
    assert diff["removed"] == []
    assert diff["changed_fields"] == []
    assert diff["numeric_delta"] == {}


def test_report_diff_detects_node_and_edge_count_changes():
    before = _sample_report()
    after = _sample_report()
    after["graph_summary"] = dict(after["graph_summary"])
    after["graph_summary"]["node_count"] = 4
    after["graph_summary"]["edge_count"] = 5

    diff = build_mesh_context_report_diff(before, after)

    assert diff["changed"] is True
    assert "node_count" in diff["changed_fields"]
    assert "edge_count" in diff["changed_fields"]
    assert diff["numeric_delta"]["node_count"] == 1
    assert diff["numeric_delta"]["edge_count"] == 3


def test_type_breakdown_changes_are_detected_when_computed_from_records():
    before = {
        "nodes": [
            {"id": "a", "type": "class"},
            {"id": "b", "type": "function"},
        ],
        "edges": [{"source": "a", "target": "b", "relation": "calls"}],
    }
    after = {
        "nodes": [
            {"id": "a", "type": "class"},
            {"id": "b", "type": "function"},
            {"id": "c", "type": "method"},
        ],
        "edges": [
            {"source": "a", "target": "b", "relation": "calls"},
            {"source": "c", "target": "b", "relation": "imports"},
        ],
    }

    diff = build_mesh_context_report_diff(before, after)

    assert diff["after"]["node_type_breakdown"] == {
        "class": 1,
        "function": 1,
        "method": 1,
    }
    assert "node_type_breakdown.method" in diff["added"]
    assert "edge_type_breakdown.imports" in diff["added"]
    assert diff["numeric_delta"]["node_count"] == 1
    assert diff["numeric_delta"]["edge_count"] == 1


def test_no_filesystem_writes_are_performed(monkeypatch):
    def fail_open(*args, **kwargs):
        raise AssertionError("benchmark diff helpers must not access filesystem")

    monkeypatch.setattr(builtins, "open", fail_open)

    before = _sample_report()
    after = _sample_report()
    after["graph_summary"] = dict(after["graph_summary"], node_count=4)

    diff = build_mesh_context_report_diff(before, after)

    assert diff["changed"] is True


def test_absolute_paths_are_redacted_from_vector_and_diff():
    report = {
        "nodes": [
            {"id": "C:\\Users\\M S I\\secret.py", "type": "C:\\Users\\M S I\\type.py"},
            {"id": "/home/dev/private.py", "type": "class"},
        ],
        "dependency_summary": {
            "C:\\Users\\M S I\\dep.py": 1,
            "safe_count": 2,
            "top_files": ["/home/dev/private.py"],
        },
    }

    vector = build_mesh_context_benchmark_vector(report)
    diff = build_mesh_context_report_diff(report, report)
    dumped = json.dumps({"vector": vector, "diff": diff}, sort_keys=True)

    assert "C:\\Users" not in dumped
    assert "/home/dev" not in dumped
    assert "__unsafe_redacted__" in dumped
