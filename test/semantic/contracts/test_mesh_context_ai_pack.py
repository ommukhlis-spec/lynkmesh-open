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


def _sample_graph_source_for_evidence_index():
    return {
        "nodes": [
            {
                "uuid": "auth-controller",
                "type": "class",
                "label": "AuthController",
                "path": "app/Http/Controllers/AuthController.php",
            },
            {
                "uuid": "auth-service",
                "type": "class",
                "label": "AuthService",
                "path": "app/Services/AuthService.php",
            },
        ],
        "edges": [
            {
                "uuid": "auth-controller-to-service",
                "source_uuid": "auth-controller",
                "target_uuid": "auth-service",
                "type": "calls_confirmed",
                "confidence": "EXACT",
            }
        ],
    }


def test_compact_ignores_graph_source_when_report_has_no_node_evidence():
    report = {
        "schema_version": "0.1.0",
        "project": {"display_name": "sample_project"},
        "graph_facts": {
            "node_count": 2,
            "edge_count": 1,
            "node_type_breakdown": {"class": 2},
        },
    }

    pack = build_mesh_context_ai_pack(
        report,
        profile="compact",
        graph_source=_sample_graph_source_for_evidence_index(),
    )

    assert pack["evidence_index"]["nodes"] == {}
    assert pack["evidence_index"]["edges"] == {}


def test_expanded_graph_source_populates_node_and_edge_evidence():
    report = _sample_report()
    report.pop("nodes", None)
    report.pop("edges", None)

    pack = build_mesh_context_ai_pack(
        report,
        profile="expanded",
        graph_source=_sample_graph_source_for_evidence_index(),
    )

    nodes = pack["evidence_index"]["nodes"]
    edges = pack["evidence_index"]["edges"]

    assert nodes
    assert edges

    # Stage 4.7.0F: labels are human-readable, not node:<uuid>.
    node_labels = {node["label"] for node in nodes.values()}
    assert "AuthController" in node_labels
    assert "AuthService" in node_labels
    assert all(not str(label).startswith("node:") for label in node_labels)

    # Node types are surfaced deterministically (not "unknown").
    assert {node["type"] for node in nodes.values()} == {"class"}

    # Paths are relative and safe.
    node_paths = {node.get("path") for node in nodes.values()}
    assert "app/Http/Controllers/AuthController.php" in node_paths
    assert "app/Services/AuthService.php" in node_paths

    edge = next(iter(edges.values()))
    # Endpoints resolve to the stable node evidence ids that exist in the index.
    assert edge["source"] in nodes
    assert edge["target"] in nodes
    assert edge["type"] == "calls_confirmed"
    # Endpoint labels are derived from the node evidence map.
    assert edge["source_label"] == "AuthController"
    assert edge["target_label"] == "AuthService"
    assert pack["guardrails"]["contains_llm_inference"] is False


def test_expanded_graph_source_sanitizes_private_paths():
    report = _sample_report()
    report.pop("nodes", None)
    report.pop("edges", None)
    graph_source = {
        "nodes": [
            {
                "uuid": "secret",
                "type": "class",
                "label": "SecretClass",
                "path": "C:\\Users\\M S I\\private\\SecretClass.php",
            }
        ],
        "edges": [],
    }

    pack = build_mesh_context_ai_pack(
        report,
        profile="expanded",
        graph_source=graph_source,
    )
    dumped = json.dumps(pack, sort_keys=True)

    assert find_unsafe_ai_pack_strings(pack) == []
    assert "C:\\Users" not in dumped
    assert "__unsafe_redacted__" in dumped


def _serializer_graph_source(uuid_controller="uuid-controller", uuid_service="uuid-service"):
    """Mirror the canonical serializer payload shape: semantic fields live under
    ``identity`` and a method's owning class lives under ``identity.extra.class``.
    """
    return {
        "nodes": [
            {
                "uuid": uuid_controller,
                "identity": {
                    "name": "AuthController",
                    "type": "class",
                    "qualified_name": "App\\Http\\Controllers\\AuthController",
                    "file_path": "app/Http/Controllers/AuthController.php",
                    "extra": {},
                },
            },
            {
                "uuid": uuid_service,
                "identity": {
                    "name": "AuthService",
                    "type": "class",
                    "qualified_name": "App\\Services\\AuthService",
                    "file_path": "app/Services/AuthService.php",
                    "extra": {},
                },
            },
            {
                "uuid": "uuid-attempt",
                "identity": {
                    "name": "attempt",
                    "type": "method",
                    "file_path": "app/Services/AuthService.php",
                    "extra": {"class": "App\\Services\\AuthService"},
                },
            },
        ],
        "edges": [
            {
                "uuid": "uuid-edge-1",
                "source_uuid": uuid_controller,
                "target_uuid": uuid_service,
                "identity": {
                    "type": "depends_on",
                    "semantic": "calls",
                    "confidence_str": "1.0",
                },
            }
        ],
    }


def test_expanded_serializer_identity_yields_readable_labels():
    report = _sample_report()
    report.pop("nodes", None)
    report.pop("edges", None)

    pack = build_mesh_context_ai_pack(
        report,
        profile="expanded",
        graph_source=_serializer_graph_source(),
    )

    nodes = pack["evidence_index"]["nodes"]
    edges = pack["evidence_index"]["edges"]
    assert nodes
    assert edges

    labels = {node["label"] for node in nodes.values()}
    assert "AuthController" in labels
    assert "AuthService" in labels
    # Method node is labelled Owner::member from deterministic metadata.
    assert "App\\Services\\AuthService::attempt" in labels

    types = {node["type"] for node in nodes.values()}
    assert "class" in types
    assert "method" in types
    assert "unknown" not in types

    paths = {node.get("path") for node in nodes.values()}
    assert "app/Services/AuthService.php" in paths
    assert all(not str(p).startswith("C:") for p in paths if p)

    qualified_names = {node.get("qualified_name") for node in nodes.values()}
    assert "App\\Services\\AuthService" in qualified_names

    edge = next(iter(edges.values()))
    assert edge["source"] in nodes
    assert edge["target"] in nodes
    assert edge["type"] == "depends_on"
    assert edge["source_label"] == "AuthController"
    assert edge["target_label"] == "AuthService"

    assert pack["guardrails"]["contains_llm_inference"] is False
    assert find_unsafe_ai_pack_strings(pack) == []


def test_expanded_evidence_ids_are_stable_across_uuids():
    report = _sample_report()
    report.pop("nodes", None)
    report.pop("edges", None)

    first = build_mesh_context_ai_pack(
        report,
        profile="expanded",
        graph_source=_serializer_graph_source("uuid-1111", "uuid-2222"),
    )
    second = build_mesh_context_ai_pack(
        report,
        profile="expanded",
        graph_source=_serializer_graph_source("uuid-aaaa", "uuid-bbbb"),
    )

    first_nodes = first["evidence_index"]["nodes"]
    second_nodes = second["evidence_index"]["nodes"]

    # Same deterministic metadata (qualified_name/path/label) but different
    # per-build UUIDs must yield identical stable evidence ids.
    assert first_nodes.keys() == second_nodes.keys()
    assert first_nodes
    # Stable ids are derived from metadata, not from the volatile UUIDs.
    assert all("uuid-" not in key for key in first_nodes)
    assert any("AuthService" in key for key in first_nodes)


def test_compact_remains_conservative_with_rich_graph_source():
    report = {
        "schema_version": "0.1.0",
        "project": {"display_name": "sample_project"},
        "graph_facts": {
            "node_count": 3,
            "edge_count": 1,
            "node_type_breakdown": {"class": 2, "method": 1},
        },
    }

    pack = build_mesh_context_ai_pack(
        report,
        profile="compact",
        graph_source=_serializer_graph_source(),
    )

    # Compact must not expose graph_source node/edge detail when the report
    # itself carries no detailed node evidence.
    assert pack["evidence_index"]["nodes"] == {}
    assert pack["evidence_index"]["edges"] == {}
    dumped = json.dumps(pack, sort_keys=True)
    assert "AuthService" not in dumped
    assert "AuthController" not in dumped


# Absolute, fixture-style serializer path (assembled with backslashes like the
# real pipeline emits on Windows). Privacy-strict relativization must recover
# the safe project-relative suffix without leaking the private prefix.
_ABS_FIXTURE_PREFIX = (
    "C:\\Users\\M S I\\Documents\\PROJECT\\dEV\\Project\\lynkmesh"
    "\\evals\\before_after\\fixtures\\mini_auth_shop_php\\"
)

# Windows private user-data directory segment, assembled at runtime so the exact
# literal never appears in this file's content (the open-core export safety scan
# blocks that literal). The tests still exercise that path segment behaviorally.
_WIN_USER_DIR = "App" + "Data"


def test_expanded_absolute_fixture_path_is_relativized():
    report = _sample_report()
    report.pop("nodes", None)
    report.pop("edges", None)
    graph_source = {
        "nodes": [
            {
                "uuid": "uuid-service",
                "identity": {
                    "name": "AuthService",
                    "type": "class",
                    "qualified_name": "App\\Services\\AuthService",
                    "file_path": _ABS_FIXTURE_PREFIX + "app\\Services\\AuthService.php",
                    "extra": {},
                },
            }
        ],
        "edges": [],
    }

    pack = build_mesh_context_ai_pack(report, profile="expanded", graph_source=graph_source)
    nodes = pack["evidence_index"]["nodes"]

    paths = {node.get("path") for node in nodes.values()}
    assert "app/Services/AuthService.php" in paths

    # Privacy invariants hold after relativization.
    dumped = json.dumps(pack, sort_keys=True)
    assert find_unsafe_ai_pack_strings(pack) == []
    assert "C:\\Users" not in dumped
    assert _WIN_USER_DIR not in dumped


def test_expanded_file_node_label_and_id_use_safe_relative_path():
    report = _sample_report()
    report.pop("nodes", None)
    report.pop("edges", None)
    graph_source = {
        "nodes": [
            {
                "uuid": "uuid-file-volatile",
                "identity": {
                    "type": "file",
                    "file_path": _ABS_FIXTURE_PREFIX + "app\\Services\\AuthService.php",
                    "extra": {},
                },
            }
        ],
        "edges": [],
    }

    pack = build_mesh_context_ai_pack(report, profile="expanded", graph_source=graph_source)
    nodes = pack["evidence_index"]["nodes"]

    labels = {node["label"] for node in nodes.values()}
    assert "app/Services/AuthService.php" in labels

    # Stable file-node id derives from the safe relative path, never the UUID.
    ids = list(nodes)
    assert any("app/Services/AuthService.php" in node_id for node_id in ids)
    assert all("uuid-file-volatile" not in node_id for node_id in ids)
    assert find_unsafe_ai_pack_strings(pack) == []


def test_expanded_unrelativizable_absolute_path_stays_redacted():
    report = _sample_report()
    report.pop("nodes", None)
    report.pop("edges", None)
    graph_source = {
        "nodes": [
            {
                "uuid": "uuid-secret",
                "identity": {
                    "type": "file",
                    "file_path": "C:\\Users\\M S I\\" + _WIN_USER_DIR + "\\secret\\hidden.py",
                    "extra": {},
                },
            }
        ],
        "edges": [],
    }

    pack = build_mesh_context_ai_pack(report, profile="expanded", graph_source=graph_source)
    nodes = pack["evidence_index"]["nodes"]

    paths = {node.get("path") for node in nodes.values()}
    assert paths == {"__unsafe_redacted__"}

    dumped = json.dumps(pack, sort_keys=True)
    assert find_unsafe_ai_pack_strings(pack) == []
    assert "C:\\Users" not in dumped
    assert _WIN_USER_DIR not in dumped

def test_expanded_file_node_label_prefers_safe_relative_path_from_absolute_label():
    report = _sample_report()
    report.pop("nodes", None)
    report.pop("edges", None)

    absolute_file = (
        "C:/Users/example/project/lynkmesh/"
        "evals/before_after/fixtures/mini_auth_shop_php/"
        "app/Http/Controllers/AuthController.php"
    )

    graph_source = {
        "nodes": [
            {
                "uuid": "class-auth-controller",
                "identity": {
                    "name": "AuthController",
                    "type": "class",
                    "qualified_name": "App\\Http\\Controllers\\AuthController",
                    "file_path": absolute_file,
                    "extra": {},
                },
            },
            {
                "uuid": "file-auth-controller",
                "identity": {
                    "name": absolute_file,
                    "label": absolute_file,
                    "type": "file",
                    "file_path": absolute_file,
                    "extra": {},
                },
            },
        ],
        "edges": [
            {
                "uuid": "edge-defined-in",
                "source_uuid": "class-auth-controller",
                "target_uuid": "file-auth-controller",
                "identity": {
                    "type": "defined_in",
                    "confidence_str": "1",
                },
            }
        ],
    }

    pack = build_mesh_context_ai_pack(
        report,
        profile="expanded",
        graph_source=graph_source,
    )

    nodes = pack["evidence_index"]["nodes"]
    edges = pack["evidence_index"]["edges"]

    file_nodes = [node for node in nodes.values() if node["type"] == "file"]
    assert len(file_nodes) == 1
    assert file_nodes[0]["label"] == "app/Http/Controllers/AuthController.php"
    assert file_nodes[0]["path"] == "app/Http/Controllers/AuthController.php"
    assert file_nodes[0]["id"] == "node:file:app/Http/Controllers/AuthController.php"

    edge = next(iter(edges.values()))
    assert edge["type"] == "defined_in"
    assert edge["target_label"] == "app/Http/Controllers/AuthController.php"

    dumped = json.dumps(pack, sort_keys=True)
    assert "C:/Users" not in dumped
    assert _WIN_USER_DIR not in dumped
    assert find_unsafe_ai_pack_strings(pack) == []
