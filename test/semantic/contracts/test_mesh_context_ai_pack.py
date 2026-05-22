import builtins
import json

import pytest

from semantic.contracts.mesh_context_ai_pack import (
    MESH_CONTEXT_AI_PACK_PURPOSE,
    MESH_CONTEXT_AI_PACK_SCHEMA_VERSION,
    build_mesh_context_ai_pack,
    estimate_mesh_context_tokens,
    find_unsafe_ai_pack_strings,
)


def _sample_report():
    return {
        "schema_version": "mesh_context_report.v0.1",
        "project": {
            "display_name": "sample_project",
            "language_hints": ["php"],
            "framework_hints": ["laravel"],
        },
        "build": {
            "build_id": "build-001",
            "content_hash": "sha256-demo",
        },
        "graph_id": "graph-001",
        "graph_summary": {
            "node_count": 4,
            "edge_count": 3,
            "node_type_breakdown": {"class": 2, "method": 2},
            "edge_type_breakdown": {"calls": 2, "imports": 1},
            "confidence_distribution": {"0.75-1.00": 3, "0.50-0.75": 1},
            "dependency_summary": {
                "internal_edges": 3,
                "external_edges": 0,
                "top_dependencies": ["node:controller", "node:service"],
            },
        },
        "nodes_by_uuid": {
            "controller": {
                "type": "class",
                "label": "UserController",
                "confidence": "high",
            },
            "service": {
                "type": "class",
                "label": "UserService",
                "confidence": "high",
            },
            "repository": {
                "type": "class",
                "label": "UserRepository",
                "confidence": "medium",
            },
        },
        "edges_by_uuid": {
            "edge-1": {
                "source": "controller",
                "target": "service",
                "relation": "calls",
                "confidence": "high",
            }
        },
        "hotspots": [
            {
                "id": "controller",
                "label": "UserController",
                "fan_in": 8,
                "fan_out": 12,
                "evidence_ids": ["node:controller"],
            }
        ],
        "risk_candidates": [
            {
                "id": "repository",
                "label": "UserRepository",
                "risk_level": "medium",
                "evidence_ids": ["node:repository"],
            }
        ],
    }


def test_compact_ai_context_pack_builds_from_minimal_report():
    pack = build_mesh_context_ai_pack(_sample_report(), profile="compact")

    assert pack["schema_version"] == MESH_CONTEXT_AI_PACK_SCHEMA_VERSION
    assert pack["purpose"] == MESH_CONTEXT_AI_PACK_PURPOSE
    assert pack["profile"] == "compact"
    assert pack["project_identity"]["display_name"] == "sample_project"
    assert pack["project_identity"]["build_id"] == "build-001"
    assert pack["project_identity"]["graph_id"] == "graph-001"
    assert pack["executive_context"]["node_count"] == 4
    assert pack["executive_context"]["edge_count"] == 3
    assert pack["hotspot_context"]["included_count"] == 1
    assert pack["risk_context"]["included_count"] == 1


def test_missing_optional_sections_produce_stable_empty_structures():
    pack = build_mesh_context_ai_pack({})

    assert pack["project_identity"]["display_name"] == "unknown"
    assert pack["executive_context"]["node_count"] == 0
    assert pack["executive_context"]["edge_count"] == 0
    assert pack["executive_context"]["node_type_breakdown"] == {}
    assert pack["architecture_context"]["dominant_components"] == []
    assert pack["hotspot_context"]["items"] == []
    assert pack["risk_context"]["items"] == []
    assert pack["dependency_context"]["summary"] == {}
    assert pack["evidence_index"]["nodes"] == {}


def test_same_input_produces_identical_output():
    first = build_mesh_context_ai_pack(_sample_report())
    second = build_mesh_context_ai_pack(_sample_report())

    assert first == second
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_profile_names_are_validated():
    with pytest.raises(ValueError, match="Unsupported MeshContext AI pack profile"):
        build_mesh_context_ai_pack(_sample_report(), profile="tiny")


@pytest.mark.parametrize("profile", ["compact", "balanced", "expanded"])
def test_supported_profiles_build(profile):
    pack = build_mesh_context_ai_pack(_sample_report(), profile=profile)

    assert pack["profile"] == profile
    assert pack["context_budget"]["profile"] == profile


def test_token_estimate_is_deterministic():
    payload = {"b": [1, 2, 3], "a": "stable"}

    assert estimate_mesh_context_tokens(payload) == estimate_mesh_context_tokens(payload)
    assert estimate_mesh_context_tokens(payload) > 0


def test_token_reduction_metadata_is_stable():
    report = _sample_report()
    report["large_raw_section"] = [
        {"id": f"node-{idx}", "body": "x" * 200}
        for idx in range(20)
    ]

    pack = build_mesh_context_ai_pack(report, profile="compact")
    budget = pack["context_budget"]

    assert budget["estimator"] == "deterministic_char_heuristic_v0.1"
    assert budget["estimated_source_report_tokens"] >= budget["estimated_input_tokens"]
    assert budget["estimated_token_reduction_percent"] >= 0


def test_guardrails_are_always_present():
    pack = build_mesh_context_ai_pack({})

    assert pack["guardrails"] == {
        "deterministic_facts_only": True,
        "contains_llm_inference": False,
        "llm_interpretation_not_included": True,
        "must_cite_evidence_ids": True,
        "do_not_infer_business_logic_without_evidence": True,
        "do_not_assume_unseen_source_code": True,
    }


def test_evidence_ids_are_preserved_when_source_ids_exist():
    pack = build_mesh_context_ai_pack(_sample_report())

    assert "node:controller" in pack["evidence_index"]["nodes"]
    assert "node:repository" in pack["evidence_index"]["nodes"]
    assert pack["hotspot_context"]["items"][0]["evidence_ids"] == ["node:controller"]
    assert pack["risk_context"]["items"][0]["evidence_ids"] == ["node:repository"]


def test_unsafe_paths_are_redacted_and_detectable():
    report = {
        "project": {"display_name": "C:\\Users\\M S I\\secret-project"},
        "nodes": [
            {"id": "C:\\Users\\M S I\\secret.py", "type": "class"},
            {"id": "/home/dev/private.py", "type": "service"},
        ],
        "dependency_summary": {
            "C:\\Users\\M S I\\dep.py": 1,
            "top_dependencies": ["/home/dev/private.py"],
        },
    }

    unsafe_source = find_unsafe_ai_pack_strings(report)
    pack = build_mesh_context_ai_pack(report)
    dumped = json.dumps(pack, sort_keys=True)

    assert unsafe_source
    assert find_unsafe_ai_pack_strings(pack) == []
    assert "C:\\Users" not in dumped
    assert "/home/dev" not in dumped
    assert "__unsafe_redacted__" in dumped


def test_builder_performs_no_filesystem_writes(monkeypatch):
    def fail_open(*args, **kwargs):
        raise AssertionError("AI context pack builder must not access filesystem")

    monkeypatch.setattr(builtins, "open", fail_open)

    pack = build_mesh_context_ai_pack(_sample_report())

    assert pack["schema_version"] == MESH_CONTEXT_AI_PACK_SCHEMA_VERSION
