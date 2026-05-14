# lynkmesh/test/unit/core/test_graph_serializer.py
"""
Stage 3.1.0 — Unit tests for graph_serializer.py

Synthetic fixtures only. No GraphCore integration. No filesystem.

Test organization:
    Section 1: Public API contract (return type, schema_version, keys)
    Section 2: Pre-condition errors (None, missing finalization, bad type)
    Section 3: Deterministic ordering (nodes/edges sorted by identity)
    Section 4: UUID-free identity (per-build UUID does not affect output)
    Section 5: Content hash consistency (G4)
    Section 6: JSON round-trip (output is json.dumps/loads stable)
    Section 7: Cross-call determinism (same input → identical output)
"""

from __future__ import annotations

import json
import pytest

from lynkmesh.core.graph_core import GraphCore
from lynkmesh.core.graph_serializer import (
    serialize_graph,
    serialize_graph_to_json,
    get_serialized_content_hash,
    SERIALIZER_SCHEMA_VERSION,
    SERIALIZER_TOP_LEVEL_KEYS,
    GraphNotFinalizedError,
    SerializerConsistencyError,
)
from lynkmesh.core.graph_version import JSON_SERIALIZATION_OPTIONS


# =============================================================================
# Fixtures
# =============================================================================

def _build_minimal_finalized_graph() -> GraphCore:
    """Build a minimal but realistic finalized GraphCore."""
    g = GraphCore()
    # Class + 2 methods + external symbol
    cls_id = g.add_node(
        node_type="class",
        name="App\\Foo",
        qualified_name="App\\Foo",
        file_path="src/Foo.php",
        layer="service",
        extra={"extends": "BaseFoo", "interfaces": []},
    )
    m1_id = g.add_node(
        node_type="method",
        name="bar",
        qualified_name="App\\Foo::bar",
        file_path="src/Foo.php",
        layer="service",
        extra={"class": "App\\Foo", "visibility": "public"},
    )
    m2_id = g.add_node(
        node_type="method",
        name="baz",
        qualified_name="App\\Foo::baz",
        file_path="src/Foo.php",
        layer="service",
        extra={"class": "App\\Foo", "visibility": "private"},
    )
    ext_id = g.add_node(
        node_type="external",
        name="Carbon::now",
        qualified_name="Carbon::now",
        extra={"target_class": "Carbon", "method": "now"},
    )
    # Edges: contains + 2 calls
    g.add_edge(cls_id, m1_id, "contains", semantic="structural_contains")
    g.add_edge(cls_id, m2_id, "contains", semantic="structural_contains")
    g.add_edge(m1_id, m2_id, "calls_confirmed", confidence=0.9,
               metadata={"line": 25, "call_type": "method_call"})
    g.add_edge(m2_id, ext_id, "calls_external", confidence=0.3)

    # Finalize
    g._assign_initial_metadata(project_path="/test/proj")
    g._finalize_content_hash()
    return g


def _build_unfinalized_graph() -> GraphCore:
    """Build a graph without finalization."""
    g = GraphCore()
    g.add_node(node_type="class", name="X", qualified_name="X",
               file_path="src/X.php", layer="unknown")
    return g


# =============================================================================
# SECTION 1 — Public API contract
# =============================================================================

class TestPublicAPIContract:

    def test_returns_dict(self):
        g = _build_minimal_finalized_graph()
        result = serialize_graph(g)
        assert isinstance(result, dict)

    def test_top_level_keys_exact(self):
        g = _build_minimal_finalized_graph()
        result = serialize_graph(g)
        assert set(result.keys()) == set(SERIALIZER_TOP_LEVEL_KEYS)

    def test_schema_version_correct(self):
        g = _build_minimal_finalized_graph()
        result = serialize_graph(g)
        assert result["schema_version"] == SERIALIZER_SCHEMA_VERSION
        assert SERIALIZER_SCHEMA_VERSION == "3.1.0"

    def test_version_block_is_graph_version_to_dict(self):
        g = _build_minimal_finalized_graph()
        result = serialize_graph(g)
        assert result["version"] == g.version.to_dict()

    def test_stats_block_matches_graph_stats(self):
        g = _build_minimal_finalized_graph()
        result = serialize_graph(g)
        assert result["stats"] == g.stats()

    def test_nodes_is_list(self):
        g = _build_minimal_finalized_graph()
        result = serialize_graph(g)
        assert isinstance(result["nodes"], list)

    def test_edges_is_list(self):
        g = _build_minimal_finalized_graph()
        result = serialize_graph(g)
        assert isinstance(result["edges"], list)

    def test_node_count_matches_graph(self):
        g = _build_minimal_finalized_graph()
        result = serialize_graph(g)
        assert len(result["nodes"]) == len(g.nodes)

    def test_edge_count_matches_graph(self):
        g = _build_minimal_finalized_graph()
        result = serialize_graph(g)
        assert len(result["edges"]) == len(g.edges)

    def test_each_node_entry_has_identity_and_uuid(self):
        g = _build_minimal_finalized_graph()
        result = serialize_graph(g)
        for entry in result["nodes"]:
            assert set(entry.keys()) == {"identity", "uuid"}
            assert isinstance(entry["identity"], dict)
            assert isinstance(entry["uuid"], str)

    def test_each_edge_entry_has_identity_uuid_source_target(self):
        g = _build_minimal_finalized_graph()
        result = serialize_graph(g)
        for entry in result["edges"]:
            assert set(entry.keys()) == {
                "identity", "uuid", "source_uuid", "target_uuid"
            }


# =============================================================================
# SECTION 2 — Pre-condition errors
# =============================================================================

class TestPreConditionErrors:

    def test_none_graph_raises_type_error(self):
        with pytest.raises(TypeError, match="must not be None"):
            serialize_graph(None)

    def test_non_graph_object_raises_type_error(self):
        with pytest.raises(TypeError):
            serialize_graph("not a graph")

    def test_object_missing_nodes_attribute_raises(self):
        class Fake:
            edges = []
        with pytest.raises(TypeError):
            serialize_graph(Fake())

    def test_unfinalized_graph_raises_graph_not_finalized(self):
        g = _build_unfinalized_graph()
        with pytest.raises(GraphNotFinalizedError):
            serialize_graph(g)

    def test_empty_graph_finalized_serializes(self):
        """Empty graph that has been finalized produces valid output."""
        g = GraphCore()
        g._assign_initial_metadata(project_path="/empty")
        g._finalize_content_hash()
        result = serialize_graph(g)
        assert result["nodes"] == []
        assert result["edges"] == []
        assert "version" in result


# =============================================================================
# SECTION 3 — Deterministic ordering
# =============================================================================

class TestDeterministicOrdering:

    def test_nodes_sorted_by_identity_json(self):
        g = _build_minimal_finalized_graph()
        result = serialize_graph(g)
        identity_jsons = [
            json.dumps(n["identity"], **JSON_SERIALIZATION_OPTIONS)
            for n in result["nodes"]
        ]
        assert identity_jsons == sorted(identity_jsons)

    def test_edges_sorted_by_identity_json(self):
        g = _build_minimal_finalized_graph()
        result = serialize_graph(g)
        identity_jsons = [
            json.dumps(e["identity"], **JSON_SERIALIZATION_OPTIONS)
            for e in result["edges"]
        ]
        assert identity_jsons == sorted(identity_jsons)

    def test_same_input_produces_byte_stable_json(self):
        g = _build_minimal_finalized_graph()
        s1 = serialize_graph_to_json(g)
        s2 = serialize_graph_to_json(g)
        assert s1 == s2

    def test_multiple_serialize_calls_return_equal_dicts(self):
        g = _build_minimal_finalized_graph()
        r1 = serialize_graph(g)
        r2 = serialize_graph(g)
        assert r1 == r2


# =============================================================================
# SECTION 4 — UUID-free identity (G3)
# =============================================================================

class TestUUIDFreeIdentity:

    def test_node_identity_does_not_contain_uuid_key(self):
        g = _build_minimal_finalized_graph()
        result = serialize_graph(g)
        for entry in result["nodes"]:
            assert "id" not in entry["identity"]
            assert "uuid" not in entry["identity"]

    def test_edge_identity_does_not_contain_uuid_key(self):
        g = _build_minimal_finalized_graph()
        result = serialize_graph(g)
        for entry in result["edges"]:
            assert "id" not in entry["identity"]
            assert "from" not in entry["identity"]
            assert "to" not in entry["identity"]
            # Identity uses source_identity / target_identity, not raw UUIDs
            assert "source_identity" in entry["identity"]
            assert "target_identity" in entry["identity"]

    def test_two_graphs_same_semantics_different_uuids_same_node_identities(self):
        """Two builds of same logical graph produce same node identities."""
        g_a = _build_minimal_finalized_graph()
        g_b = _build_minimal_finalized_graph()
        # Same fixture → different UUIDs (uuid4 in add_node) but same semantics
        result_a = serialize_graph(g_a)
        result_b = serialize_graph(g_b)
        identities_a = [n["identity"] for n in result_a["nodes"]]
        identities_b = [n["identity"] for n in result_b["nodes"]]
        assert identities_a == identities_b

    def test_two_graphs_same_semantics_different_uuids_same_edge_identities(self):
        g_a = _build_minimal_finalized_graph()
        g_b = _build_minimal_finalized_graph()
        result_a = serialize_graph(g_a)
        result_b = serialize_graph(g_b)
        identities_a = [e["identity"] for e in result_a["edges"]]
        identities_b = [e["identity"] for e in result_b["edges"]]
        assert identities_a == identities_b

    def test_two_graphs_same_semantics_same_content_hash(self):
        g_a = _build_minimal_finalized_graph()
        g_b = _build_minimal_finalized_graph()
        h_a = get_serialized_content_hash(g_a)
        h_b = get_serialized_content_hash(g_b)
        assert h_a == h_b


# =============================================================================
# SECTION 5 — Content hash consistency (G4)
# =============================================================================

class TestContentHashConsistency:

    def test_serializer_recomputes_matching_content_hash(self):
        """G4: serializer's internal recomputation matches graph.version."""
        g = _build_minimal_finalized_graph()
        # serialize_graph internally re-derives content_hash and verifies.
        # If we call without exception, the invariant held.
        result = serialize_graph(g)
        assert result["version"]["content_hash"] == g.version.content_hash

    def test_post_finalize_mutation_triggers_consistency_error(self):
        """If graph is mutated after finalization, serializer detects drift."""
        g = _build_minimal_finalized_graph()
        # Mutate: add a node after finalization
        g.add_node(
            node_type="method",
            name="post_finalize",
            qualified_name="App\\Foo::post_finalize",
            file_path="src/Foo.php",
            layer="service",
            extra={"class": "App\\Foo"},
        )
        # graph.version still references pre-mutation hash, but serializer
        # recomputes from current state. They should disagree.
        with pytest.raises(SerializerConsistencyError):
            serialize_graph(g)


# =============================================================================
# SECTION 6 — JSON round-trip
# =============================================================================

class TestJsonRoundTrip:

    def test_serialize_to_json_returns_string(self):
        g = _build_minimal_finalized_graph()
        s = serialize_graph_to_json(g)
        assert isinstance(s, str)

    def test_json_string_parseable_back_to_equal_dict(self):
        g = _build_minimal_finalized_graph()
        result = serialize_graph(g)
        s = serialize_graph_to_json(g)
        reparsed = json.loads(s)
        assert reparsed == result

    def test_json_string_byte_stable_across_calls(self):
        g = _build_minimal_finalized_graph()
        s1 = serialize_graph_to_json(g)
        s2 = serialize_graph_to_json(g)
        s3 = serialize_graph_to_json(g)
        assert s1 == s2 == s3

    def test_json_string_uses_pinned_options(self):
        """Output uses no whitespace between separators (pinned config)."""
        g = _build_minimal_finalized_graph()
        s = serialize_graph_to_json(g)
        # Pinned separators are (",", ":") — no spaces
        assert ", " not in s
        assert ": " not in s


# =============================================================================
# SECTION 7 — Cross-call determinism
# =============================================================================

class TestCrossCallDeterminism:

    def test_get_serialized_content_hash_matches_version(self):
        g = _build_minimal_finalized_graph()
        assert get_serialized_content_hash(g) == g.version.content_hash

    def test_get_serialized_content_hash_stable(self):
        g = _build_minimal_finalized_graph()
        h1 = get_serialized_content_hash(g)
        h2 = get_serialized_content_hash(g)
        assert h1 == h2

    def test_serializer_does_not_mutate_graph(self):
        g = _build_minimal_finalized_graph()
        nodes_before = dict(g.nodes)
        edges_before = list(g.edges)
        version_before = g.version
        serialize_graph(g)
        assert g.nodes == nodes_before
        assert g.edges == edges_before
        assert g.version == version_before


# =============================================================================
# SECTION 8 — Schema version exposure
# =============================================================================

class TestSchemaVersionExposure:

    def test_schema_version_is_module_constant(self):
        assert SERIALIZER_SCHEMA_VERSION == "3.1.0"

    def test_top_level_keys_constant_exposed(self):
        assert SERIALIZER_TOP_LEVEL_KEYS == (
            "schema_version", "version", "stats", "nodes", "edges",
        )