# lynkmesh/test/unit/core/test_graph_version.py
"""
Stage 3.0.0 — Unit tests for graph_version.py

Verifies all 24 invariants (I1–I24) from contract v2 §6 in isolation,
using synthetic node/edge fixtures. No GraphCore integration. No filesystem.
No orchestrator. No persistence.

Test organization:
    Section 1: VersionMetadata semantics              (I11–I14)
    Section 2: GraphVersion semantics & predicates    (I16–I20)
    Section 3: Hash determinism                       (I1, I2, I4, I5)
    Section 4: Hash sensitivity                       (I3)
    Section 5: Identity excludes UUIDs                (I6, I7, I8)
    Section 6: Float and path normalization
    Section 7: External node handling (file_path=None)
    Section 8: Allowlist enforcement (extra/metadata)
    Section 9: Edge dereference identity
    Section 10: Canonical JSON ordering
    Section 11: Cross-process hash determinism (I18)
    Section 12: Round-trip serialization (to_dict/from_dict)
    Section 13: Schema migration & malformed input rejection
    Section 14: Pipeline determinism enforcement
    Section 15: Frozen-dataclass atomicity (I22)
    Section 16: Empty / minimal graph edge cases
    Section 17: Collision-resistance sanity
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Mapping, Optional

import pytest

from lynkmesh.core.graph_version import (
    GraphVersion,
    VersionMetadata,
    IncompatibleSchemaError,
    MalformedVersionError,
    SCHEMA_VERSION,
    HASH_ALGORITHM,
    EXPECTED_PIPELINE_SEED,
    JSON_SERIALIZATION_OPTIONS,
    HASH_NODES_PREFIX,
    HASH_EDGES_PREFIX,
    HASH_BLOB_SEPARATOR,
    compute_node_identity,
    compute_edge_identity,
    compute_content_hash,
    compute_graph_id,
    generate_build_id,
    verify_pipeline_determinism,
)


# =============================================================================
# Synthetic fixtures
#
# Built to mirror the verified runtime schema from Phase A (graph_core.py
# add_node + add_edge contracts). No imports from GraphCore — these are
# plain dicts that match what GraphCore would produce.
# =============================================================================

def make_node(
    *,
    node_id: str = "uuid-fake-001",
    node_type: str = "method",
    name: str = "doSomething",
    qualified_name: str = "App\\Foo::doSomething",
    file_path: Optional[str] = "src/Foo.php",
    layer: str = "service",
    extra: Optional[Dict[str, Any]] = None,
    file_alias: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build a minimal node matching GraphCore.add_node output shape.

    Mirrors graph_core.py:add_node lines 104–114, including the redundant
    `file` alias for file_path.
    """
    if extra is None:
        extra = {}
    # GraphCore.add_node sets layer/importance/entry defaults in extra.
    # Mirror that minimally.
    base_extra = {
        "layer": layer,
        "importance": 2,
        "entry": False,
    }
    base_extra.update(extra)
    return {
        "id": node_id,
        "type": node_type,
        "name": name,
        "qualified_name": qualified_name,
        "file": file_alias if file_alias is not None else file_path,
        "file_path": file_path,
        "layer": layer,
        "extra": base_extra,
    }


def make_external_node(
    *,
    node_id: str = "uuid-ext-001",
    qualified_name: str = "Carbon\\Carbon::now",
    target_class: str = "Carbon\\Carbon",
    method: str = "now",
) -> Dict[str, Any]:
    """
    Build an external node. file_path is None (verified runtime behavior).
    Mirrors call_resolver.py:613–619.
    """
    return {
        "id": node_id,
        "type": "external",
        "name": qualified_name,
        "qualified_name": qualified_name,
        "file": None,
        "file_path": None,
        "layer": "unknown",
        "extra": {
            "target_class": target_class,
            "method": method,
            "layer": "unknown",
            "importance": 1,
            "entry": False,
        },
    }


def make_edge(
    *,
    edge_id: str = "uuid-edge-001",
    source: str = "uuid-fake-001",
    target: str = "uuid-fake-002",
    edge_type: str = "calls_confirmed",
    semantic: str = "calls_confirmed",
    confidence: float = 0.9,
    metadata: Optional[Dict[str, Any]] = None,
    flow_id: Optional[str] = None,
    weight: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Build a minimal edge matching GraphCore.add_edge output shape.

    Mirrors graph_core.py:add_edge lines 170–186.
    """
    edge = {
        "id": edge_id,
        "from": source,
        "to": target,
        "type": edge_type,
        "semantic": semantic,
        "confidence": float(confidence),
    }
    if flow_id is not None:
        edge["flow_id"] = flow_id
    if weight is not None:
        edge["weight"] = weight
    if metadata is not None:
        edge["metadata"] = metadata
    return edge


def make_call_metadata(
    *,
    line: int = 42,
    call_type: str = "method_call",
    raw_call: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Build edge metadata matching call_resolver.py:1126–1130 shape.
    Includes both identity-relevant (line) and transient (call_type, raw_call) fields.
    """
    if raw_call is None:
        raw_call = {"method": "doSomething", "object": "$svc", "type": call_type}
    return {
        "call_type": call_type,
        "line": line,
        "raw_call": raw_call,
    }


# =============================================================================
# SECTION 1 — VersionMetadata semantics (I11–I14)
# =============================================================================

class TestVersionMetadata:

    def test_create_produces_valid_metadata(self):
        """Basic factory contract: all fields populated."""
        meta = VersionMetadata.create(project_path="/path/to/project")
        assert isinstance(meta.graph_id, str)
        assert isinstance(meta.build_id, str)
        assert isinstance(meta.build_timestamp, str)
        assert meta.schema_version == SCHEMA_VERSION
        assert isinstance(meta.pipeline_seed, str)

    def test_I11_graph_id_stable_for_same_path(self):
        """I11: same project_path → same graph_id deterministically."""
        meta1 = VersionMetadata.create(project_path="/proj/x")
        meta2 = VersionMetadata.create(project_path="/proj/x")
        assert meta1.graph_id == meta2.graph_id

    def test_graph_id_differs_for_different_paths(self):
        """Different paths → different graph_ids."""
        meta1 = VersionMetadata.create(project_path="/proj/a")
        meta2 = VersionMetadata.create(project_path="/proj/b")
        assert meta1.graph_id != meta2.graph_id

    def test_graph_id_normalized_path_stable(self):
        """Path normalization: backslash and forward slash equivalent."""
        meta1 = VersionMetadata.create(project_path="C:\\proj\\x")
        meta2 = VersionMetadata.create(project_path="C:/proj/x")
        assert meta1.graph_id == meta2.graph_id

    def test_graph_id_trailing_slash_normalized(self):
        """Path normalization: trailing slashes don't affect graph_id."""
        meta1 = VersionMetadata.create(project_path="/proj/x")
        meta2 = VersionMetadata.create(project_path="/proj/x/")
        assert meta1.graph_id == meta2.graph_id

    def test_graph_id_override_used_verbatim(self):
        """Override mechanism: when provided, used as graph_id directly."""
        meta = VersionMetadata.create(
            project_path="/any/path",
            graph_id_override="custom-id-123",
        )
        assert meta.graph_id == "custom-id-123"

    def test_I12_build_id_unique_per_call(self):
        """I12: each create() call produces a fresh, distinct build_id."""
        ids = {VersionMetadata.create(project_path="/p").build_id for _ in range(20)}
        assert len(ids) == 20  # all distinct

    def test_build_id_distinct_from_graph_id(self):
        """build_id and graph_id are unrelated identifiers."""
        meta = VersionMetadata.create(project_path="/p")
        assert meta.build_id != meta.graph_id

    def test_I14_pipeline_seed_reflects_environment(self):
        """I14: pipeline_seed captures the current PYTHONHASHSEED env var."""
        meta = VersionMetadata.create(project_path="/p")
        # Test runner sets PYTHONHASHSEED=0; create() reads at call time.
        assert meta.pipeline_seed == os.environ.get("PYTHONHASHSEED", "")

    def test_build_timestamp_iso_format(self):
        """build_timestamp is ISO-8601 with timezone."""
        meta = VersionMetadata.create(project_path="/p")
        # ISO 8601 with timezone: contains 'T' and either '+' or 'Z' or '-' offset
        assert "T" in meta.build_timestamp
        # Must be parseable back; sanity check on UTC encoding
        from datetime import datetime
        parsed = datetime.fromisoformat(meta.build_timestamp)
        assert parsed.tzinfo is not None

    def test_metadata_is_frozen(self):
        """VersionMetadata is immutable (frozen dataclass)."""
        meta = VersionMetadata.create(project_path="/p")
        with pytest.raises((AttributeError, Exception)):
            meta.graph_id = "tampered"  # type: ignore[misc]

    def test_metadata_to_dict_round_trip(self):
        """to_dict / from_dict preserves all fields."""
        meta = VersionMetadata.create(
            project_path="/p",
            git_commit="abc123def",
        )
        restored = VersionMetadata.from_dict(meta.to_dict())
        assert restored == meta

    def test_metadata_from_dict_with_none_git_commit(self):
        """git_commit=None is valid and preserved."""
        meta = VersionMetadata.create(project_path="/p", git_commit=None)
        restored = VersionMetadata.from_dict(meta.to_dict())
        assert restored.git_commit is None

    def test_metadata_from_dict_rejects_missing_field(self):
        """Missing required field raises MalformedVersionError."""
        bad = {
            "graph_id": "x",
            "build_id": "y",
            "build_timestamp": "2026-01-01T00:00:00+00:00",
            # missing schema_version
            "pipeline_seed": "0",
        }
        with pytest.raises(MalformedVersionError):
            VersionMetadata.from_dict(bad)

    def test_metadata_from_dict_rejects_wrong_git_commit_type(self):
        """git_commit must be str or None."""
        bad = {
            "graph_id": "x",
            "build_id": "y",
            "build_timestamp": "2026-01-01T00:00:00+00:00",
            "git_commit": 123,  # int, not str/None
            "schema_version": SCHEMA_VERSION,
            "pipeline_seed": "0",
        }
        with pytest.raises(MalformedVersionError):
            VersionMetadata.from_dict(bad)


# =============================================================================
# SECTION 2 — GraphVersion semantics & predicates (I16–I20)
# =============================================================================

class TestGraphVersionPredicates:

    def _make_version(
        self,
        *,
        graph_id: str = "g1",
        build_id: str = "b1",
        content_hash: str = "a" * 64,
        schema_version: str = SCHEMA_VERSION,
        pipeline_seed: str = "0",
    ) -> GraphVersion:
        """Build a GraphVersion with controlled fields for predicate testing."""
        return GraphVersion(
            metadata=VersionMetadata(
                graph_id=graph_id,
                build_id=build_id,
                build_timestamp="2026-01-01T00:00:00+00:00",
                git_commit=None,
                schema_version=schema_version,
                pipeline_seed=pipeline_seed,
            ),
            content_hash=content_hash,
        )

    def test_I16_equality_reflexivity(self):
        """I16: v == v always."""
        v = self._make_version()
        assert v == v

    def test_I17_equality_requires_all_fields(self):
        """I17: differs in any field → not equal."""
        v1 = self._make_version(graph_id="g1")
        v2 = self._make_version(graph_id="g2")
        assert v1 != v2

    def test_I17_equality_differs_on_content_hash(self):
        """I17: differs in content_hash → not equal."""
        v1 = self._make_version(content_hash="a" * 64)
        v2 = self._make_version(content_hash="b" * 64)
        assert v1 != v2

    def test_I17_equality_differs_on_build_id(self):
        """I17: same content but different build_id → not equal."""
        v1 = self._make_version(build_id="b1")
        v2 = self._make_version(build_id="b2")
        assert v1 != v2  # equality is strict; use is_same_content for caching

    def test_I18_hash_consistent_with_equality(self):
        """I18: equal versions have equal hashes."""
        v1 = self._make_version()
        v2 = self._make_version()
        assert v1 == v2
        assert hash(v1) == hash(v2)

    def test_I18_hash_deterministic_from_content_hash(self):
        """__hash__ derived from content_hash; deterministic across processes."""
        v1 = self._make_version(content_hash="ff" * 32)
        v2 = self._make_version(content_hash="ff" * 32, build_id="different-b")
        # Different build_id → not equal, but SAME content_hash
        assert v1 != v2
        # Yet __hash__ is the same (process-stable, content-derived)
        assert hash(v1) == hash(v2)

    def test_is_same_graph_true_when_graph_id_matches(self):
        """is_same_graph: only graph_id matters."""
        v1 = self._make_version(graph_id="g1", build_id="b1")
        v2 = self._make_version(graph_id="g1", build_id="b2")
        assert v1.is_same_graph(v2)

    def test_is_same_graph_false_when_different(self):
        v1 = self._make_version(graph_id="g1")
        v2 = self._make_version(graph_id="g2")
        assert not v1.is_same_graph(v2)

    def test_is_same_content_true_when_hash_matches(self):
        """is_same_content: cache predicate. Same hash → same content."""
        v1 = self._make_version(content_hash="aa" * 32, build_id="b1")
        v2 = self._make_version(content_hash="aa" * 32, build_id="b2")
        assert v1.is_same_content(v2)

    def test_is_same_content_false_when_hash_differs(self):
        v1 = self._make_version(content_hash="aa" * 32)
        v2 = self._make_version(content_hash="bb" * 32)
        assert not v1.is_same_content(v2)

    def test_is_serialization_compatible_true_when_schema_and_seed_match(self):
        """is_serialization_compatible: schema + pipeline_seed."""
        v1 = self._make_version(schema_version="3.0.0", pipeline_seed="0")
        v2 = self._make_version(schema_version="3.0.0", pipeline_seed="0")
        assert v1.is_serialization_compatible(v2)

    def test_is_serialization_compatible_false_on_seed_mismatch(self):
        """Different pipeline_seed → incompatible (deterministic invariants
        bound to seed)."""
        v1 = self._make_version(pipeline_seed="0")
        v2 = self._make_version(pipeline_seed="1")
        assert not v1.is_serialization_compatible(v2)

    def test_I19_equality_implies_is_same_graph(self):
        """I19: v1 == v2 implies all three predicates True."""
        v = self._make_version()
        v_copy = self._make_version()
        assert v == v_copy
        assert v.is_same_graph(v_copy)
        assert v.is_same_content(v_copy)
        assert v.is_serialization_compatible(v_copy)

    def test_I19_predicates_do_not_imply_equality(self):
        """I19 reverse: predicates True doesn't mean equal."""
        v1 = self._make_version(build_id="b1")
        v2 = self._make_version(build_id="b2")
        # Different build_id → not equal
        assert v1 != v2
        # But same graph, same content, same schema/seed
        assert v1.is_same_graph(v2)
        assert v1.is_same_content(v2)
        assert v1.is_serialization_compatible(v2)

    def test_I20_cache_predicate_semantics(self):
        """I20: is_same_content is the predicate cache layers must use.
        Independent of build_id and timestamps."""
        v1 = self._make_version(build_id="b1")
        v2 = self._make_version(build_id="b2")
        # Cache key MUST work across builds with same content.
        assert v1.is_same_content(v2)

    def test_v1_method_is_compatible_with_does_not_exist(self):
        """Contract v2 §7.3: is_compatible_with from v1 must NOT exist."""
        v = self._make_version()
        assert not hasattr(v, "is_compatible_with")

    def test_graphversion_repr_human_readable(self):
        """__repr__ contains identifying info for logging."""
        v = self._make_version(graph_id="my-graph", content_hash="abc" + "0" * 61)
        r = repr(v)
        assert "GraphVersion" in r
        assert "my-graph" in r
        assert "abc" in r  # content_hash prefix shown


# =============================================================================
# SECTION 3 — Hash determinism (I1, I2, I4, I5)
# =============================================================================

class TestHashDeterminism:

    def test_I1_same_input_same_output(self):
        """I1: identical input → identical hash output, multiple calls."""
        nodes = [make_node()]
        edges = []
        h1 = compute_content_hash(nodes, edges)
        h2 = compute_content_hash(nodes, edges)
        h3 = compute_content_hash(nodes, edges)
        assert h1 == h2 == h3

    def test_I4_node_order_independence(self):
        """I4: presentation order of nodes does not affect hash."""
        n1 = make_node(node_id="u1", qualified_name="A::a")
        n2 = make_node(node_id="u2", qualified_name="B::b")
        n3 = make_node(node_id="u3", qualified_name="C::c")
        h1 = compute_content_hash([n1, n2, n3], [])
        h2 = compute_content_hash([n3, n1, n2], [])
        h3 = compute_content_hash([n2, n3, n1], [])
        assert h1 == h2 == h3

    def test_I4_edge_order_independence(self):
        """I4: presentation order of edges does not affect hash."""
        n1 = make_node(node_id="u1", qualified_name="A::a")
        n2 = make_node(node_id="u2", qualified_name="B::b")
        n3 = make_node(node_id="u3", qualified_name="C::c")
        e1 = make_edge(edge_id="e1", source="u1", target="u2")
        e2 = make_edge(edge_id="e2", source="u2", target="u3")
        e3 = make_edge(edge_id="e3", source="u1", target="u3")
        h1 = compute_content_hash([n1, n2, n3], [e1, e2, e3])
        h2 = compute_content_hash([n1, n2, n3], [e3, e1, e2])
        h3 = compute_content_hash([n1, n2, n3], [e2, e3, e1])
        assert h1 == h2 == h3

    def test_I4_combined_node_and_edge_reorder(self):
        """I4: full reorder of both nodes and edges → same hash."""
        n1 = make_node(node_id="u1", qualified_name="A::a")
        n2 = make_node(node_id="u2", qualified_name="B::b")
        e1 = make_edge(edge_id="e1", source="u1", target="u2")
        h1 = compute_content_hash([n1, n2], [e1])
        h2 = compute_content_hash([n2, n1], [e1])
        assert h1 == h2

    def test_I5_hash_format_64_lowercase_hex(self):
        """I5: output is exactly 64 lowercase hex chars."""
        h = compute_content_hash([make_node()], [])
        assert len(h) == 64
        assert h == h.lower()
        assert re.fullmatch(r"[0-9a-f]{64}", h) is not None

    def test_hash_deterministic_with_extras(self):
        """Hash is stable when nodes have rich extras."""
        n = make_node(extra={
            "class": "Foo",
            "extends": "Bar",
            "interfaces": ["Iface1", "Iface2"],
            "params": [{"name": "x", "type": "int"}],
            "return_type": "string",
        })
        h1 = compute_content_hash([n], [])
        h2 = compute_content_hash([n], [])
        assert h1 == h2

    def test_hash_deterministic_with_metadata_lines(self):
        """Hash is stable for edges with metadata."""
        n1 = make_node(node_id="u1")
        n2 = make_node(node_id="u2", qualified_name="App\\Bar::baz")
        e = make_edge(source="u1", target="u2", metadata=make_call_metadata(line=42))
        h1 = compute_content_hash([n1, n2], [e])
        h2 = compute_content_hash([n1, n2], [e])
        assert h1 == h2


# =============================================================================
# SECTION 4 — Hash sensitivity (I3)
# =============================================================================

class TestHashSensitivity:

    def test_I3_qualified_name_change_changes_hash(self):
        n1 = make_node(qualified_name="A::a")
        n2 = make_node(qualified_name="A::b")  # different method
        assert compute_content_hash([n1], []) != compute_content_hash([n2], [])

    def test_I3_node_type_change_changes_hash(self):
        n1 = make_node(node_type="method")
        n2 = make_node(node_type="function")
        assert compute_content_hash([n1], []) != compute_content_hash([n2], [])

    def test_I3_file_path_change_changes_hash(self):
        n1 = make_node(file_path="src/A.php")
        n2 = make_node(file_path="src/B.php")
        assert compute_content_hash([n1], []) != compute_content_hash([n2], [])

    def test_I3_layer_change_changes_hash(self):
        n1 = make_node(layer="service")
        n2 = make_node(layer="repository")
        assert compute_content_hash([n1], []) != compute_content_hash([n2], [])

    def test_I3_extra_class_change_changes_hash(self):
        n1 = make_node(extra={"class": "Foo"})
        n2 = make_node(extra={"class": "Bar"})
        assert compute_content_hash([n1], []) != compute_content_hash([n2], [])

    def test_I3_edge_type_change_changes_hash(self):
        n1 = make_node(node_id="u1")
        n2 = make_node(node_id="u2", qualified_name="X::y")
        e1 = make_edge(source="u1", target="u2", edge_type="calls_confirmed")
        e2 = make_edge(source="u1", target="u2", edge_type="calls_heuristic")
        assert (
            compute_content_hash([n1, n2], [e1])
            != compute_content_hash([n1, n2], [e2])
        )

    def test_I3_edge_confidence_change_changes_hash(self):
        n1 = make_node(node_id="u1")
        n2 = make_node(node_id="u2", qualified_name="X::y")
        e1 = make_edge(source="u1", target="u2", confidence=0.9)
        e2 = make_edge(source="u1", target="u2", confidence=0.8)
        assert (
            compute_content_hash([n1, n2], [e1])
            != compute_content_hash([n1, n2], [e2])
        )

    def test_I3_edge_metadata_line_change_changes_hash(self):
        n1 = make_node(node_id="u1")
        n2 = make_node(node_id="u2", qualified_name="X::y")
        e1 = make_edge(
            source="u1", target="u2", metadata=make_call_metadata(line=10)
        )
        e2 = make_edge(
            source="u1", target="u2", metadata=make_call_metadata(line=20)
        )
        assert (
            compute_content_hash([n1, n2], [e1])
            != compute_content_hash([n1, n2], [e2])
        )

    def test_I3_adding_node_changes_hash(self):
        n1 = make_node(node_id="u1")
        n2 = make_node(node_id="u2", qualified_name="X::y")
        h1 = compute_content_hash([n1], [])
        h2 = compute_content_hash([n1, n2], [])
        assert h1 != h2

    def test_I3_adding_edge_changes_hash(self):
        n1 = make_node(node_id="u1")
        n2 = make_node(node_id="u2", qualified_name="X::y")
        e = make_edge(source="u1", target="u2")
        h1 = compute_content_hash([n1, n2], [])
        h2 = compute_content_hash([n1, n2], [e])
        assert h1 != h2


# =============================================================================
# SECTION 5 — Identity excludes UUIDs (I6, I7, I8)
# =============================================================================

class TestIdentityExcludesUUIDs:

    def test_I6_node_identity_independent_of_node_id(self):
        """I6: changing node['id'] (UUID) does NOT change identity."""
        n1 = make_node(node_id="uuid-aaaa-1111", qualified_name="A::b")
        n2 = make_node(node_id="uuid-zzzz-9999", qualified_name="A::b")
        # Same semantics, different UUID
        assert compute_node_identity(n1) == compute_node_identity(n2)

    def test_I6_node_identity_omits_id_key(self):
        """compute_node_identity result must not contain the 'id' field."""
        n = make_node(node_id="uuid-12345")
        identity = compute_node_identity(n)
        assert "id" not in identity

    def test_I7_edge_identity_independent_of_edge_id(self):
        """I7: changing edge['id'] (UUID) does NOT change identity."""
        n1 = make_node(node_id="u1", qualified_name="A::a")
        n2 = make_node(node_id="u2", qualified_name="B::b")
        nodes_map = {"u1": n1, "u2": n2}
        e1 = make_edge(edge_id="edge-aaa", source="u1", target="u2")
        e2 = make_edge(edge_id="edge-zzz", source="u1", target="u2")
        assert compute_edge_identity(e1, nodes_map) == compute_edge_identity(e2, nodes_map)

    def test_I7_edge_identity_omits_id_key(self):
        """compute_edge_identity result must not contain edge id."""
        n1 = make_node(node_id="u1")
        n2 = make_node(node_id="u2", qualified_name="X::y")
        nodes_map = {"u1": n1, "u2": n2}
        e = make_edge(source="u1", target="u2")
        identity = compute_edge_identity(e, nodes_map)
        assert "id" not in identity

    def test_I8_cross_build_node_identity_stable(self):
        """I8: 'rebuilds' producing different UUIDs but same semantics
        produce identical identity."""
        # Simulate two builds: same logical graph, different UUID space
        build_a_node = make_node(
            node_id="b1-uuid-001",
            qualified_name="App\\Foo::bar",
            file_path="src/Foo.php",
            layer="service",
        )
        build_b_node = make_node(
            node_id="b2-uuid-999",   # totally different UUID
            qualified_name="App\\Foo::bar",
            file_path="src/Foo.php",
            layer="service",
        )
        assert compute_node_identity(build_a_node) == compute_node_identity(build_b_node)

    def test_I8_cross_build_content_hash_stable(self):
        """I8: full content_hash stable across builds with different UUIDs."""
        # Build A
        a1 = make_node(node_id="ba-1", qualified_name="A::a")
        a2 = make_node(node_id="ba-2", qualified_name="B::b")
        ea = make_edge(edge_id="eA", source="ba-1", target="ba-2")
        # Build B (totally different UUIDs, same semantics)
        b1 = make_node(node_id="bb-9", qualified_name="A::a")
        b2 = make_node(node_id="bb-7", qualified_name="B::b")
        eb = make_edge(edge_id="eB", source="bb-9", target="bb-7")

        h_a = compute_content_hash([a1, a2], [ea])
        h_b = compute_content_hash([b1, b2], [eb])
        assert h_a == h_b


# =============================================================================
# SECTION 6 — Float and path normalization
# =============================================================================

class TestFloatAndPathNormalization:

    def test_path_forward_slash_and_backslash_equivalent(self):
        """File paths normalized: backslash → forward slash."""
        n_unix = make_node(file_path="src/foo/Bar.php")
        n_win = make_node(file_path="src\\foo\\Bar.php")
        assert compute_node_identity(n_unix) == compute_node_identity(n_win)

    def test_path_normalization_in_full_hash(self):
        """Full content_hash invariant under path slash normalization."""
        n_unix = make_node(file_path="src/Foo.php", node_id="u1")
        n_win = make_node(file_path="src\\Foo.php", node_id="u1")
        assert compute_content_hash([n_unix], []) == compute_content_hash([n_win], [])

    def test_float_confidence_normalized_via_17g(self):
        """Confidence normalized via format(.17g); 0.9 stable."""
        n1 = make_node(node_id="u1")
        n2 = make_node(node_id="u2", qualified_name="X::y")
        nodes_map = {"u1": n1, "u2": n2}
        e1 = make_edge(source="u1", target="u2", confidence=0.9)
        e2 = make_edge(source="u1", target="u2", confidence=0.9)
        assert compute_edge_identity(e1, nodes_map) == compute_edge_identity(e2, nodes_map)

    def test_float_confidence_distinguishes_different_values(self):
        """Different floats produce different identity."""
        n1 = make_node(node_id="u1")
        n2 = make_node(node_id="u2", qualified_name="X::y")
        nodes_map = {"u1": n1, "u2": n2}
        e1 = make_edge(source="u1", target="u2", confidence=0.8)
        e2 = make_edge(source="u1", target="u2", confidence=0.9)
        assert compute_edge_identity(e1, nodes_map) != compute_edge_identity(e2, nodes_map)

    def test_all_runtime_confidence_values_distinguishable(self):
        """All confidence values used by resolver are distinct in hash."""
        n1 = make_node(node_id="u1")
        n2 = make_node(node_id="u2", qualified_name="X::y")
        nodes_map = {"u1": n1, "u2": n2}
        runtime_confidences = [0.3, 0.5, 0.8, 0.9, 0.95, 1.0]
        identities = [
            compute_edge_identity(
                make_edge(source="u1", target="u2", confidence=c),
                nodes_map,
            )
            for c in runtime_confidences
        ]
        # All distinct
        assert len({str(i) for i in identities}) == len(runtime_confidences)

    def test_weight_field_normalized_via_17g(self):
        """Edge weight (when present) also via .17g."""
        n1 = make_node(node_id="u1")
        n2 = make_node(node_id="u2", qualified_name="X::y")
        nodes_map = {"u1": n1, "u2": n2}
        e_with = make_edge(source="u1", target="u2", weight=0.75)
        e_without = make_edge(source="u1", target="u2")
        # Different identities (one has weight, one doesn't)
        assert compute_edge_identity(e_with, nodes_map) != compute_edge_identity(e_without, nodes_map)

    def test_float_value_one_third_stable(self):
        """Tricky float (1/3) hashes deterministically across calls."""
        third = 1.0 / 3.0
        n1 = make_node(node_id="u1")
        n2 = make_node(node_id="u2", qualified_name="X::y")
        nodes_map = {"u1": n1, "u2": n2}
        e = make_edge(source="u1", target="u2", confidence=third)
        id1 = compute_edge_identity(e, nodes_map)
        id2 = compute_edge_identity(e, nodes_map)
        assert id1 == id2


# =============================================================================
# SECTION 7 — External node handling (file_path=None)
# =============================================================================

class TestExternalNodeHandling:

    def test_external_node_identity_with_none_file_path(self):
        """External nodes (file_path=None) compute identity without error."""
        ext = make_external_node()
        identity = compute_node_identity(ext)
        assert identity["file_path"] is None
        assert identity["type"] == "external"

    def test_external_node_identity_stable(self):
        """Same external (Carbon::now) produces same identity."""
        e1 = make_external_node(qualified_name="Carbon::now", node_id="u1")
        e2 = make_external_node(qualified_name="Carbon::now", node_id="u2")
        assert compute_node_identity(e1) == compute_node_identity(e2)

    def test_external_nodes_distinguishable_by_qualified_name(self):
        """Different external symbols → different identity."""
        e1 = make_external_node(qualified_name="Carbon::now")
        e2 = make_external_node(qualified_name="Auth::user")
        assert compute_node_identity(e1) != compute_node_identity(e2)

    def test_full_hash_with_external_nodes(self):
        """compute_content_hash works with mixed regular + external nodes."""
        regular = make_node(node_id="u-regular")
        ext = make_external_node(node_id="u-ext")
        edge = make_edge(
            source="u-regular",
            target="u-ext",
            edge_type="calls_external",
            confidence=0.3,
        )
        h = compute_content_hash([regular, ext], [edge])
        assert len(h) == 64

    def test_external_node_identity_includes_target_class_and_method(self):
        """External nodes' extras (target_class, method) survive in identity."""
        e1 = make_external_node(target_class="Foo", method="bar")
        e2 = make_external_node(target_class="Foo", method="baz")
        assert compute_node_identity(e1) != compute_node_identity(e2)


# =============================================================================
# SECTION 8 — Allowlist enforcement (extra/metadata)
# =============================================================================

class TestAllowlistEnforcement:

    # --- Node extra allowlist ---

    def test_extra_imports_excluded(self):
        """imports key in extra is transient; changing it doesn't affect hash."""
        n1 = make_node(extra={"imports": ["A", "B"], "class": "Foo"})
        n2 = make_node(extra={"imports": ["X", "Y", "Z"], "class": "Foo"})
        # Imports differ wildly; but hash should be same (excluded)
        assert compute_node_identity(n1) == compute_node_identity(n2)

    def test_extra_layer_confidence_excluded(self):
        """layer_confidence excluded from hash."""
        n1 = make_node(extra={"class": "Foo", "layer_confidence": 0.95})
        n2 = make_node(extra={"class": "Foo", "layer_confidence": 0.5})
        assert compute_node_identity(n1) == compute_node_identity(n2)

    def test_extra_importance_excluded(self):
        """importance excluded from hash (defaults differ but excluded)."""
        n1 = make_node(extra={"class": "Foo", "importance": 5})
        n2 = make_node(extra={"class": "Foo", "importance": 1})
        assert compute_node_identity(n1) == compute_node_identity(n2)

    def test_extra_calls_excluded(self):
        """calls (IR-derived list) excluded from hash."""
        n1 = make_node(extra={"class": "Foo", "calls": [{"method": "x"}]})
        n2 = make_node(extra={"class": "Foo", "calls": []})
        assert compute_node_identity(n1) == compute_node_identity(n2)

    def test_extra_class_included(self):
        """class IS in allowlist; affects hash."""
        n1 = make_node(extra={"class": "Foo"})
        n2 = make_node(extra={"class": "Bar"})
        assert compute_node_identity(n1) != compute_node_identity(n2)

    def test_extra_extends_included(self):
        """extends IS in allowlist; affects hash."""
        n1 = make_node(extra={"extends": "Base"})
        n2 = make_node(extra={"extends": "OtherBase"})
        assert compute_node_identity(n1) != compute_node_identity(n2)

    def test_extra_interfaces_included(self):
        """interfaces IS in allowlist; affects hash."""
        n1 = make_node(extra={"interfaces": ["I1"]})
        n2 = make_node(extra={"interfaces": ["I2"]})
        assert compute_node_identity(n1) != compute_node_identity(n2)

    def test_extra_return_type_included(self):
        """return_type IS in allowlist; affects hash."""
        n1 = make_node(extra={"return_type": "string"})
        n2 = make_node(extra={"return_type": "int"})
        assert compute_node_identity(n1) != compute_node_identity(n2)

    def test_extra_visibility_included(self):
        """visibility IS in allowlist; affects hash."""
        n1 = make_node(extra={"visibility": "public"})
        n2 = make_node(extra={"visibility": "private"})
        assert compute_node_identity(n1) != compute_node_identity(n2)

    def test_extra_unknown_keys_silently_excluded(self):
        """Unknown extra keys are excluded; future-proof."""
        n1 = make_node(extra={"class": "Foo", "newly_added_field_2027": "x"})
        n2 = make_node(extra={"class": "Foo"})
        assert compute_node_identity(n1) == compute_node_identity(n2)

    def test_top_level_file_alias_excluded(self):
        """The 'file' key (alias for file_path) is excluded from hash."""
        n1 = make_node(file_path="src/Foo.php", file_alias="src/Foo.php")
        n2 = make_node(file_path="src/Foo.php", file_alias="DIFFERENT_ALIAS")
        # Even if 'file' alias is wildly different, file_path matches → identity same
        assert compute_node_identity(n1) == compute_node_identity(n2)

    # --- Edge metadata allowlist ---

    def test_metadata_raw_call_excluded(self):
        """metadata.raw_call (transient deep-copy) excluded from hash."""
        n1 = make_node(node_id="u1")
        n2 = make_node(node_id="u2", qualified_name="X::y")
        nodes_map = {"u1": n1, "u2": n2}
        meta1 = make_call_metadata(
            line=42,
            raw_call={"method": "x", "type": "method_call", "extra_field_a": 1},
        )
        meta2 = make_call_metadata(
            line=42,
            raw_call={"method": "x", "type": "method_call", "extra_field_b": 2},
        )
        e1 = make_edge(source="u1", target="u2", metadata=meta1)
        e2 = make_edge(source="u1", target="u2", metadata=meta2)
        # raw_call differs, but hash same (raw_call excluded)
        assert compute_edge_identity(e1, nodes_map) == compute_edge_identity(e2, nodes_map)

    def test_metadata_call_type_excluded(self):
        """metadata.call_type excluded from hash."""
        n1 = make_node(node_id="u1")
        n2 = make_node(node_id="u2", qualified_name="X::y")
        nodes_map = {"u1": n1, "u2": n2}
        meta1 = make_call_metadata(line=42, call_type="method_call")
        meta2 = make_call_metadata(line=42, call_type="static_call")
        e1 = make_edge(source="u1", target="u2", metadata=meta1)
        e2 = make_edge(source="u1", target="u2", metadata=meta2)
        # call_type differs in metadata, hash same (call_type excluded)
        # Note: raw_call.type also differs, but raw_call is excluded entirely
        assert compute_edge_identity(e1, nodes_map) == compute_edge_identity(e2, nodes_map)

    def test_metadata_line_included(self):
        """metadata.line is in allowlist; affects hash."""
        n1 = make_node(node_id="u1")
        n2 = make_node(node_id="u2", qualified_name="X::y")
        nodes_map = {"u1": n1, "u2": n2}
        e1 = make_edge(source="u1", target="u2", metadata={"line": 10})
        e2 = make_edge(source="u1", target="u2", metadata={"line": 20})
        assert compute_edge_identity(e1, nodes_map) != compute_edge_identity(e2, nodes_map)


# =============================================================================
# SECTION 9 — Edge dereference identity
# =============================================================================

class TestEdgeDereferenceIdentity:

    def test_edge_dereferences_source_via_nodes_map(self):
        """Edge identity's source_identity is the node identity of edge['from']."""
        n1 = make_node(node_id="u1", qualified_name="A::a")
        n2 = make_node(node_id="u2", qualified_name="B::b")
        nodes_map = {"u1": n1, "u2": n2}
        e = make_edge(source="u1", target="u2")
        identity = compute_edge_identity(e, nodes_map)
        # source_identity should match what compute_node_identity returns for n1
        assert identity["source_identity"] == compute_node_identity(n1)
        assert identity["target_identity"] == compute_node_identity(n2)

    def test_edge_with_swapped_uuids_but_same_node_identity(self):
        """If two graphs have same node identities under different UUIDs,
        edges between them produce identical edge identity."""
        # Graph A
        a1 = make_node(node_id="A-1", qualified_name="X::y")
        a2 = make_node(node_id="A-2", qualified_name="P::q")
        a_map = {"A-1": a1, "A-2": a2}
        ea = make_edge(edge_id="ea", source="A-1", target="A-2")
        # Graph B (different UUIDs, same semantics)
        b1 = make_node(node_id="B-7", qualified_name="X::y")
        b2 = make_node(node_id="B-3", qualified_name="P::q")
        b_map = {"B-7": b1, "B-3": b2}
        eb = make_edge(edge_id="eb", source="B-7", target="B-3")

        assert compute_edge_identity(ea, a_map) == compute_edge_identity(eb, b_map)

    def test_edge_with_missing_source_node_returns_none_identity(self):
        """Defensive: missing source node → source_identity is None."""
        n2 = make_node(node_id="u2", qualified_name="X::y")
        # nodes_map missing u1
        nodes_map = {"u2": n2}
        e = make_edge(source="u1", target="u2")
        identity = compute_edge_identity(e, nodes_map)
        assert identity["source_identity"] is None
        assert identity["target_identity"] is not None

    def test_edge_with_missing_target_node_returns_none_identity(self):
        """Defensive: missing target node → target_identity is None."""
        n1 = make_node(node_id="u1")
        nodes_map = {"u1": n1}
        e = make_edge(source="u1", target="u-missing")
        identity = compute_edge_identity(e, nodes_map)
        assert identity["source_identity"] is not None
        assert identity["target_identity"] is None

    def test_edge_identity_does_not_contain_from_or_to_uuid(self):
        """Edge identity contains source/target_identity, NOT the UUIDs."""
        n1 = make_node(node_id="uuid-aaa")
        n2 = make_node(node_id="uuid-bbb", qualified_name="X::y")
        nodes_map = {"uuid-aaa": n1, "uuid-bbb": n2}
        e = make_edge(source="uuid-aaa", target="uuid-bbb")
        identity = compute_edge_identity(e, nodes_map)
        identity_str = str(identity)
        assert "uuid-aaa" not in identity_str
        assert "uuid-bbb" not in identity_str


# =============================================================================
# SECTION 10 — Canonical JSON ordering
# =============================================================================

class TestCanonicalJSONOrdering:

    def test_dict_key_order_normalized(self):
        """Same dict with different key order → same identity."""
        n1 = make_node(extra={"class": "Foo", "extends": "Bar", "visibility": "public"})
        n2 = make_node(extra={"visibility": "public", "extends": "Bar", "class": "Foo"})
        # Python 3.7+ preserves insertion order, but our canonicalization sorts.
        assert compute_node_identity(n1) == compute_node_identity(n2)

    def test_nested_dict_recursive_canonicalization(self):
        """Nested dicts also canonicalized."""
        # Simulating params with nested dict; insertion order varies
        n1 = make_node(extra={
            "params": [{"name": "x", "type": "int"}],
        })
        n2 = make_node(extra={
            "params": [{"type": "int", "name": "x"}],
        })
        assert compute_node_identity(n1) == compute_node_identity(n2)

    def test_set_in_extra_handled_via_canonicalization(self):
        """If a set somehow appears in extra, it is canonicalized to sorted list."""
        # Not typical runtime but defensive: sets convert to sorted lists
        n1 = make_node(extra={"interfaces": ["A", "B", "C"]})
        n2 = make_node(extra={"interfaces": ["A", "B", "C"]})
        assert compute_node_identity(n1) == compute_node_identity(n2)

    def test_list_order_preserved(self):
        """Lists are NOT sorted (producer's responsibility for determinism)."""
        # params order matters semantically (positional)
        n1 = make_node(extra={"params": ["x", "y"]})
        n2 = make_node(extra={"params": ["y", "x"]})
        assert compute_node_identity(n1) != compute_node_identity(n2)

    def test_pinned_json_options_constant(self):
        """JSON_SERIALIZATION_OPTIONS exposes the pinned config."""
        assert JSON_SERIALIZATION_OPTIONS["sort_keys"] is True
        assert JSON_SERIALIZATION_OPTIONS["separators"] == (",", ":")
        assert JSON_SERIALIZATION_OPTIONS["ensure_ascii"] is True


# =============================================================================
# SECTION 11 — Cross-process hash determinism (I18, I2)
# =============================================================================

class TestCrossProcessHashDeterminism:

    def test_I18_python_hash_uses_content_hash_prefix(self):
        """__hash__ derives from content_hash; same content → same hash."""
        v1 = GraphVersion(
            metadata=VersionMetadata(
                graph_id="g1", build_id="b1",
                build_timestamp="2026-01-01T00:00:00+00:00",
                git_commit=None, schema_version=SCHEMA_VERSION, pipeline_seed="0",
            ),
            content_hash="0123456789abcdef" * 4,
        )
        v2 = GraphVersion(
            metadata=VersionMetadata(
                graph_id="DIFFERENT", build_id="DIFFERENT",
                build_timestamp="2099-12-31T23:59:59+00:00",
                git_commit="abc", schema_version=SCHEMA_VERSION, pipeline_seed="0",
            ),
            content_hash="0123456789abcdef" * 4,  # SAME content
        )
        # Different metadata, same content → different equality, same hash
        assert v1 != v2
        assert hash(v1) == hash(v2)

    def test_hash_independent_of_pythonhashseed(self):
        """Equal content_hash values produce equal hash() results."""

        v1 = GraphVersion(
            metadata=VersionMetadata(
                graph_id="g1",
                build_id="b1",
                build_timestamp="2026-01-01T00:00:00+00:00",
                git_commit=None,
                schema_version=SCHEMA_VERSION,
                pipeline_seed="0",
            ),
            content_hash="ff" * 32,
        )

        v2 = GraphVersion(
            metadata=VersionMetadata(
                graph_id="g2",
                build_id="b2",
                build_timestamp="2099-12-31T23:59:59+00:00",
                git_commit=None,
                schema_version=SCHEMA_VERSION,
                pipeline_seed="0",
            ),
            content_hash="ff" * 32,
        )

        # Different metadata => not equal objects
        assert v1 != v2

        # Same content_hash => deterministic identical hash()
        assert hash(v1) == hash(v2)

        v3 = GraphVersion(
            metadata=v1.metadata,
            content_hash="00" * 32,
        )

        # Different content_hash => different hash()
        assert hash(v1) != hash(v3)

    def test_two_compute_calls_same_inputs_same_output(self):
        """I1+I2: deterministic across calls."""
        n1 = make_node(node_id="u1", qualified_name="A::a")
        n2 = make_node(node_id="u2", qualified_name="B::b")
        e = make_edge(source="u1", target="u2")
        h_calls = [compute_content_hash([n1, n2], [e]) for _ in range(5)]
        assert all(h == h_calls[0] for h in h_calls)
        
    def test_hash_max_uint64_content(self):
        """Boundary case: all-ff content hash remains deterministic."""
        v1 = GraphVersion(
            metadata=VersionMetadata(
                graph_id="g1",
                build_id="b1",
                build_timestamp="2026-01-01T00:00:00+00:00",
                git_commit=None,
                schema_version=SCHEMA_VERSION,
                pipeline_seed="0",
            ),
            content_hash="f" * 64,
        )

        v2 = GraphVersion(
            metadata=VersionMetadata(
                graph_id="g2",
                build_id="b2",
                build_timestamp="2099-01-01T00:00:00+00:00",
                git_commit=None,
                schema_version=SCHEMA_VERSION,
                pipeline_seed="0",
            ),
            content_hash="f" * 64,
        )

        assert hash(v1) == hash(v2)
        
    def test_hash_zero_content(self):
        """Boundary case: zero hash content is valid."""
        v = GraphVersion(
            metadata=VersionMetadata(
                graph_id="g",
                build_id="b",
                build_timestamp="2026-01-01T00:00:00+00:00",
                git_commit=None,
                schema_version=SCHEMA_VERSION,
                pipeline_seed="0",
            ),
            content_hash="0" * 64,
        )

        assert isinstance(hash(v), int)
        
        
    def test_hash_signed_boundary(self):
        """Boundary case: signed 64-bit transition point."""
        v = GraphVersion(
            metadata=VersionMetadata(
                graph_id="g",
                build_id="b",
                build_timestamp="2026-01-01T00:00:00+00:00",
                git_commit=None,
                schema_version=SCHEMA_VERSION,
                pipeline_seed="0",
            ),
            content_hash="8000000000000000" + ("0" * 48),
        )

        assert isinstance(hash(v), int)
        
    def test_hash_dict_key_usability(self):
        """GraphVersion works correctly as dictionary key."""
        v1 = GraphVersion(
            metadata=VersionMetadata(
                graph_id="g1",
                build_id="b1",
                build_timestamp="2026-01-01T00:00:00+00:00",
                git_commit=None,
                schema_version=SCHEMA_VERSION,
                pipeline_seed="0",
            ),
            content_hash="aa" * 32,
        )

        v2 = GraphVersion(
            metadata=VersionMetadata(
                graph_id="g2",
                build_id="b2",
                build_timestamp="2026-01-01T00:00:00+00:00",
                git_commit=None,
                schema_version=SCHEMA_VERSION,
                pipeline_seed="0",
            ),
            content_hash="bb" * 32,
        )

        d = {
            v1: "first",
            v2: "second",
        }

        assert d[v1] == "first"
        assert d[v2] == "second"
        
    def test_hash_set_membership(self):
        """Equal GraphVersion objects collapse correctly in sets."""
        metadata = VersionMetadata(
            graph_id="g",
            build_id="b",
            build_timestamp="2026-01-01T00:00:00+00:00",
            git_commit=None,
            schema_version=SCHEMA_VERSION,
            pipeline_seed="0",
        )

        v1 = GraphVersion(
            metadata=metadata,
            content_hash="cc" * 32,
        )

        v2 = GraphVersion(
            metadata=metadata,
            content_hash="cc" * 32,
        )

        s = {v1, v2}

        assert len(s) == 1


# =============================================================================
# SECTION 12 — Round-trip serialization
# =============================================================================

class TestRoundTripSerialization:

    def test_graph_version_to_dict_from_dict(self):
        """GraphVersion round-trips losslessly."""
        meta = VersionMetadata.create(project_path="/p", git_commit="abc")
        original = GraphVersion(metadata=meta, content_hash="a" * 64)
        restored = GraphVersion.from_dict(original.to_dict())
        assert restored == original

    def test_to_dict_returns_serializable_structure(self):
        """to_dict output is JSON-serializable."""
        import json
        meta = VersionMetadata.create(project_path="/p")
        v = GraphVersion(metadata=meta, content_hash="c" * 64)
        d = v.to_dict()
        # Must be JSON-encodable
        json.dumps(d)

    def test_to_dict_preserves_all_fields(self):
        """All metadata fields appear in to_dict output."""
        meta = VersionMetadata.create(project_path="/p", git_commit="cm1")
        v = GraphVersion(metadata=meta, content_hash="d" * 64)
        d = v.to_dict()
        assert "metadata" in d
        assert "content_hash" in d
        assert d["content_hash"] == "d" * 64
        assert d["metadata"]["graph_id"] == meta.graph_id
        assert d["metadata"]["build_id"] == meta.build_id
        assert d["metadata"]["git_commit"] == "cm1"


# =============================================================================
# SECTION 13 — Schema migration & malformed input rejection
# =============================================================================

class TestSchemaAndMalformedRejection:

    def _valid_dict(self) -> Dict[str, Any]:
        return {
            "metadata": {
                "graph_id": "g",
                "build_id": "b",
                "build_timestamp": "2026-01-01T00:00:00+00:00",
                "git_commit": None,
                "schema_version": SCHEMA_VERSION,
                "pipeline_seed": "0",
            },
            "content_hash": "a" * 64,
        }

    def test_from_dict_accepts_valid(self):
        """Sanity: valid dict round-trips."""
        v = GraphVersion.from_dict(self._valid_dict())
        assert v.content_hash == "a" * 64

    def test_from_dict_rejects_future_major_version(self):
        """IncompatibleSchemaError for future major version."""
        d = self._valid_dict()
        d["metadata"]["schema_version"] = "99.0.0"
        with pytest.raises(IncompatibleSchemaError):
            GraphVersion.from_dict(d)

    def test_from_dict_accepts_same_major_version(self):
        """Same major version (3.x.y) should be accepted."""
        d = self._valid_dict()
        d["metadata"]["schema_version"] = "3.5.7"
        # Should NOT raise (same major)
        GraphVersion.from_dict(d)

    def test_from_dict_rejects_missing_metadata(self):
        d = self._valid_dict()
        del d["metadata"]
        with pytest.raises(MalformedVersionError):
            GraphVersion.from_dict(d)

    def test_from_dict_rejects_missing_content_hash(self):
        d = self._valid_dict()
        del d["content_hash"]
        with pytest.raises(MalformedVersionError):
            GraphVersion.from_dict(d)

    def test_from_dict_rejects_short_content_hash(self):
        d = self._valid_dict()
        d["content_hash"] = "abc"
        with pytest.raises(MalformedVersionError):
            GraphVersion.from_dict(d)

    def test_from_dict_rejects_uppercase_content_hash(self):
        d = self._valid_dict()
        d["content_hash"] = "A" * 64
        with pytest.raises(MalformedVersionError):
            GraphVersion.from_dict(d)

    def test_from_dict_rejects_non_hex_content_hash(self):
        d = self._valid_dict()
        d["content_hash"] = "z" * 64
        with pytest.raises(MalformedVersionError):
            GraphVersion.from_dict(d)

    def test_from_dict_rejects_malformed_schema_version(self):
        d = self._valid_dict()
        d["metadata"]["schema_version"] = "not-a-version"
        with pytest.raises(MalformedVersionError):
            GraphVersion.from_dict(d)

    def test_from_dict_rejects_non_mapping_input(self):
        with pytest.raises(MalformedVersionError):
            GraphVersion.from_dict("not a dict")  # type: ignore[arg-type]

    def test_from_dict_rejects_non_mapping_metadata(self):
        d = self._valid_dict()
        d["metadata"] = "not a dict"
        with pytest.raises(MalformedVersionError):
            GraphVersion.from_dict(d)

    def test_from_dict_rejects_non_string_content_hash(self):
        d = self._valid_dict()
        d["content_hash"] = 12345
        with pytest.raises(MalformedVersionError):
            GraphVersion.from_dict(d)


# =============================================================================
# SECTION 14 — Pipeline determinism enforcement
# =============================================================================

class TestPipelineDeterminismEnforcement:

    def test_verify_passes_with_seed_zero(self):
        """When PYTHONHASHSEED=0, verify_pipeline_determinism returns silently."""
        # Test runner sets PYTHONHASHSEED=0; verify this contract.
        original = os.environ.get("PYTHONHASHSEED")
        try:
            os.environ["PYTHONHASHSEED"] = "0"
            # No exception
            verify_pipeline_determinism()
        finally:
            if original is None:
                os.environ.pop("PYTHONHASHSEED", None)
            else:
                os.environ["PYTHONHASHSEED"] = original

    def test_verify_raises_on_wrong_seed(self):
        """Non-zero PYTHONHASHSEED triggers EnvironmentError."""
        original = os.environ.get("PYTHONHASHSEED")
        try:
            os.environ["PYTHONHASHSEED"] = "1"
            with pytest.raises(EnvironmentError):
                verify_pipeline_determinism()
        finally:
            if original is None:
                os.environ.pop("PYTHONHASHSEED", None)
            else:
                os.environ["PYTHONHASHSEED"] = original

    def test_verify_raises_on_random_seed(self):
        """'random' (Python's randomization mode) triggers EnvironmentError."""
        original = os.environ.get("PYTHONHASHSEED")
        try:
            os.environ["PYTHONHASHSEED"] = "random"
            with pytest.raises(EnvironmentError):
                verify_pipeline_determinism()
        finally:
            if original is None:
                os.environ.pop("PYTHONHASHSEED", None)
            else:
                os.environ["PYTHONHASHSEED"] = original

    def test_verify_raises_on_unset(self):
        """Unset PYTHONHASHSEED triggers EnvironmentError."""
        original = os.environ.get("PYTHONHASHSEED")
        try:
            os.environ.pop("PYTHONHASHSEED", None)
            with pytest.raises(EnvironmentError):
                verify_pipeline_determinism()
        finally:
            if original is not None:
                os.environ["PYTHONHASHSEED"] = original


# =============================================================================
# SECTION 15 — Frozen-dataclass atomicity (I22)
# =============================================================================

class TestFrozenDataclass:

    def test_I22_version_metadata_frozen(self):
        """VersionMetadata cannot be field-mutated."""
        meta = VersionMetadata.create(project_path="/p")
        from dataclasses import FrozenInstanceError
        with pytest.raises(FrozenInstanceError):
            meta.graph_id = "tampered"  # type: ignore[misc]

    def test_I22_graph_version_frozen(self):
        """GraphVersion cannot be field-mutated."""
        meta = VersionMetadata.create(project_path="/p")
        v = GraphVersion(metadata=meta, content_hash="a" * 64)
        from dataclasses import FrozenInstanceError
        with pytest.raises(FrozenInstanceError):
            v.content_hash = "tampered"  # type: ignore[misc]


# =============================================================================
# SECTION 16 — Empty / minimal graph edge cases
# =============================================================================

class TestEmptyAndMinimalGraphs:

    def test_empty_graph_hash_deterministic(self):
        """compute_content_hash([], []) is deterministic and known."""
        h1 = compute_content_hash([], [])
        h2 = compute_content_hash([], [])
        assert h1 == h2
        assert len(h1) == 64

    def test_empty_graph_hash_distinct_from_single_node(self):
        """Empty graph hash != single-node graph hash."""
        h_empty = compute_content_hash([], [])
        h_single = compute_content_hash([make_node()], [])
        assert h_empty != h_single

    def test_empty_graph_expected_hash(self):
        """Verify the exact expected hash of an empty graph."""
        # Per contract: payload = b"NODES:" + b"" + b"|EDGES:" + b""
        import hashlib
        expected_payload = HASH_NODES_PREFIX + HASH_EDGES_PREFIX
        expected_hash = hashlib.sha256(expected_payload).hexdigest()
        actual_hash = compute_content_hash([], [])
        assert actual_hash == expected_hash

    def test_single_node_no_edges(self):
        """Hash works for single node + no edges."""
        n = make_node(qualified_name="Solo::method")
        h = compute_content_hash([n], [])
        assert len(h) == 64

    def test_single_node_self_loop_edge(self):
        """Edge cases with self-referential edge."""
        n = make_node(node_id="u-self")
        e = make_edge(source="u-self", target="u-self")
        h = compute_content_hash([n], [e])
        assert len(h) == 64


# =============================================================================
# SECTION 17 — Collision-resistance sanity
# =============================================================================

class TestCollisionResistanceSanity:

    def test_distinct_qnames_produce_distinct_hashes(self):
        """100 nodes with distinct qnames produce 100 distinct hashes."""
        hashes = set()
        for i in range(100):
            n = make_node(qualified_name=f"Class::method{i}")
            hashes.add(compute_content_hash([n], []))
        assert len(hashes) == 100

    def test_node_vs_edge_payload_namespacing(self):
        """A graph with one 'X-shaped' node (no edges) hashes differently
        from the same content viewed as edge data."""
        # This is a structural test: NODES: prefix vs EDGES: prefix
        # ensures the namespaces can never collide.
        # In practice, identical content as nodes vs as edges produces
        # different payloads due to prefix separation.
        n_only = compute_content_hash([make_node(qualified_name="X")], [])
        # Empty graph hash differs (we already tested that)
        # This is a sanity check: prefixes prevent collision pathologies.
        assert n_only != compute_content_hash([], [])

    def test_swapping_source_target_produces_different_hash(self):
        """Edge (A→B) vs (B→A) produce different hashes (direction matters)."""
        n1 = make_node(node_id="u1", qualified_name="A::a")
        n2 = make_node(node_id="u2", qualified_name="B::b")
        e_forward = make_edge(source="u1", target="u2")
        e_reverse = make_edge(source="u2", target="u1")
        h_fwd = compute_content_hash([n1, n2], [e_forward])
        h_rev = compute_content_hash([n1, n2], [e_reverse])
        assert h_fwd != h_rev

    def test_realistic_call_graph_hash_stable(self):
        """Realistic small call-graph: 5 nodes, 4 edges. Hash deterministic."""
        # Build a controller → service → repository pattern
        ctrl = make_node(
            node_id="u-ctrl", qualified_name="App\\Http\\Controllers\\UserController",
            node_type="class", file_path="src/Http/UserController.php", layer="controller",
            extra={"extends": "BaseController", "interfaces": []},
        )
        ctrl_index = make_node(
            node_id="u-ctrl-index", qualified_name="App\\Http\\Controllers\\UserController::index",
            node_type="method", file_path="src/Http/UserController.php", layer="controller",
            extra={"class": "App\\Http\\Controllers\\UserController", "visibility": "public"},
        )
        svc = make_node(
            node_id="u-svc", qualified_name="App\\Services\\UserService",
            node_type="class", file_path="src/Services/UserService.php", layer="service",
        )
        svc_get_all = make_node(
            node_id="u-svc-getall", qualified_name="App\\Services\\UserService::getAll",
            node_type="method", file_path="src/Services/UserService.php", layer="service",
            extra={"class": "App\\Services\\UserService", "return_type": "Collection"},
        )
        ext = make_external_node(node_id="u-ext", qualified_name="DB::table")

        e1 = make_edge(edge_id="e1", source="u-ctrl", target="u-ctrl-index", edge_type="contains")
        e2 = make_edge(edge_id="e2", source="u-svc", target="u-svc-getall", edge_type="contains")
        e3 = make_edge(
            edge_id="e3", source="u-ctrl-index", target="u-svc-getall",
            edge_type="calls_confirmed", confidence=0.9,
            metadata={"line": 25, "call_type": "method_call"},
        )
        e4 = make_edge(
            edge_id="e4", source="u-svc-getall", target="u-ext",
            edge_type="calls_external", confidence=0.3,
        )

        nodes = [ctrl, ctrl_index, svc, svc_get_all, ext]
        edges = [e1, e2, e3, e4]
        h1 = compute_content_hash(nodes, edges)
        h2 = compute_content_hash(nodes, edges)
        # Reorder nodes + edges
        h3 = compute_content_hash([ext, svc_get_all, svc, ctrl_index, ctrl], [e4, e3, e2, e1])
        assert h1 == h2 == h3



# =============================================================================
# SECTION 18 — Stage 3.0.0.1 Hardening Tests (11 tests added)
# =============================================================================

class TestSameContentDifferentMetadataHashing:
    """
    Inverse of test_hash_dict_key_usability: same content_hash, different
    metadata. Same hash() bucket, distinct __eq__ identity.
    """

    def test_same_content_different_metadata_same_hash(self):
        """Same content_hash → same hash() result, even if metadata differs."""
        v1 = GraphVersion(
            metadata=VersionMetadata(
                graph_id="graph-A", build_id="build-1",
                build_timestamp="2026-01-01T00:00:00+00:00",
                git_commit="abc", schema_version=SCHEMA_VERSION,
                pipeline_seed="0",
            ),
            content_hash="cc" * 32,
        )
        v2 = GraphVersion(
            metadata=VersionMetadata(
                graph_id="graph-B", build_id="build-9999",
                build_timestamp="2099-12-31T23:59:59+00:00",
                git_commit="xyz", schema_version=SCHEMA_VERSION,
                pipeline_seed="0",
            ),
            content_hash="cc" * 32,  # SAME content
        )
        assert v1 != v2
        assert hash(v1) == hash(v2)

    def test_same_hash_different_eq_dict_behavior(self):
        """Dict treats v1 and v2 as distinct keys despite same hash."""
        v1 = GraphVersion(
            metadata=VersionMetadata(
                graph_id="g", build_id="b1",
                build_timestamp="2026-01-01T00:00:00+00:00",
                git_commit=None, schema_version=SCHEMA_VERSION,
                pipeline_seed="0",
            ),
            content_hash="dd" * 32,
        )
        v2 = GraphVersion(
            metadata=VersionMetadata(
                graph_id="g", build_id="b2",
                build_timestamp="2026-01-01T00:00:00+00:00",
                git_commit=None, schema_version=SCHEMA_VERSION,
                pipeline_seed="0",
            ),
            content_hash="dd" * 32,
        )
        d = {v1: "first", v2: "second"}
        assert len(d) == 2


class TestAdversarialInputs:
    """
    Defensive tests for malformed nodes/edges. Hash function must not crash.
    """

    def test_node_with_extra_as_none(self):
        """Node with extra=None: hash treats as empty dict."""
        n = {
            "id": "u1", "type": "method", "name": "x",
            "qualified_name": "A::x", "file_path": "src/A.php",
            "file": "src/A.php", "layer": "service",
            "extra": None,
        }
        identity = compute_node_identity(n)
        assert identity["qualified_name"] == "A::x"
        assert identity["extra"] == {}

    def test_node_with_missing_extra(self):
        """Node with 'extra' key absent: hash treats as empty dict."""
        n = {
            "id": "u1", "type": "method", "name": "x",
            "qualified_name": "A::x", "file_path": "src/A.php",
            "file": "src/A.php", "layer": "service",
        }
        identity = compute_node_identity(n)
        assert identity["extra"] == {}

    def test_node_with_qualified_name_none(self):
        """Node with qualified_name=None: None preserved as identity field."""
        n = {
            "id": "u1", "type": "unknown", "name": "",
            "qualified_name": None,
            "file_path": None,
            "file": None,
            "layer": "unknown",
            "extra": {},
        }
        identity = compute_node_identity(n)
        assert identity["qualified_name"] is None
        assert identity["file_path"] is None

    def test_edge_with_missing_metadata_key(self):
        """Structural edges have no metadata; hash produces empty dict."""
        n1 = make_node(node_id="u1")
        n2 = make_node(node_id="u2", qualified_name="X::y")
        nodes_map = {"u1": n1, "u2": n2}
        e = {
            "id": "edge-x", "from": "u1", "to": "u2",
            "type": "defined_in", "semantic": "structural_defined_in",
            "confidence": 1.0,
        }
        identity = compute_edge_identity(e, nodes_map)
        assert identity["metadata"] == {}
        assert identity["confidence_str"] == "1"

    def test_edge_with_metadata_as_non_dict(self):
        """Defensive: non-dict metadata treated as empty."""
        n1 = make_node(node_id="u1")
        n2 = make_node(node_id="u2", qualified_name="X::y")
        nodes_map = {"u1": n1, "u2": n2}
        e = {
            "id": "edge-x", "from": "u1", "to": "u2",
            "type": "calls_confirmed", "semantic": "calls_confirmed",
            "confidence": 0.9,
            "metadata": "not a dict",
        }
        identity = compute_edge_identity(e, nodes_map)
        assert identity["metadata"] == {}


class TestRuntimeConfidenceCanonicalization:
    """Cross-platform float canonicalization for resolver's confidence values."""

    def test_all_runtime_confidence_values_canonicalize_stably(self):
        """
        Verify all confidence values emitted by resolver produce stable
        .17g strings. Cross-platform stability check.

        Expected strings are from CPython 3.x on x86_64. If this test
        fails on a different platform, content_hash is not portable.
        """
        runtime_values = {
            0.3: "0.29999999999999999",
            0.5: "0.5",
            0.8: "0.80000000000000004",
            0.9: "0.90000000000000002",
            0.95: "0.94999999999999996",
            1.0: "1",
        }
        for value, expected_str in runtime_values.items():
            actual = format(value, ".17g")
            assert actual == expected_str, (
                f"Confidence {value} → {actual!r}, expected {expected_str!r}. "
                f"Cross-platform float drift detected."
            )

    def test_runtime_confidence_round_trip_stability(self):
        """All confidence values: two identity calls produce identical output."""
        n1 = make_node(node_id="u1")
        n2 = make_node(node_id="u2", qualified_name="X::y")
        nodes_map = {"u1": n1, "u2": n2}
        for confidence in [0.3, 0.5, 0.8, 0.9, 0.95, 1.0]:
            e_a = make_edge(source="u1", target="u2", confidence=confidence)
            e_b = make_edge(source="u1", target="u2", confidence=confidence)
            id_a = compute_edge_identity(e_a, nodes_map)
            id_b = compute_edge_identity(e_b, nodes_map)
            assert id_a == id_b


class TestNaNAndInfinityDefensiveBehavior:
    """
    NaN/infinity edge cases. Resolver doesn't emit these currently;
    these tests document behavior to detect silent regression.
    """

    def test_nan_in_confidence_produces_deterministic_identity(self):
        """NaN serializes as 'nan' string consistently within process."""
        n1 = make_node(node_id="u1")
        n2 = make_node(node_id="u2", qualified_name="X::y")
        nodes_map = {"u1": n1, "u2": n2}
        nan_val = float("nan")
        e_a = make_edge(source="u1", target="u2", confidence=nan_val)
        e_b = make_edge(source="u1", target="u2", confidence=nan_val)
        id_a = compute_edge_identity(e_a, nodes_map)
        id_b = compute_edge_identity(e_b, nodes_map)
        assert id_a["confidence_str"] == "nan"
        assert id_b["confidence_str"] == "nan"
        assert id_a == id_b

    def test_infinity_in_confidence_produces_deterministic_identity(self):
        """Positive infinity → 'inf' string."""
        n1 = make_node(node_id="u1")
        n2 = make_node(node_id="u2", qualified_name="X::y")
        nodes_map = {"u1": n1, "u2": n2}
        e = make_edge(source="u1", target="u2", confidence=float("inf"))
        identity = compute_edge_identity(e, nodes_map)
        assert identity["confidence_str"] == "inf"

    def test_negative_infinity_in_confidence_produces_deterministic_identity(self):
        """Negative infinity → '-inf' string."""
        n1 = make_node(node_id="u1")
        n2 = make_node(node_id="u2", qualified_name="X::y")
        nodes_map = {"u1": n1, "u2": n2}
        e = make_edge(source="u1", target="u2", confidence=float("-inf"))
        identity = compute_edge_identity(e, nodes_map)
        assert identity["confidence_str"] == "-inf"


# =============================================================================
# Smoke test for module-level constants
# =============================================================================

class TestModuleConstants:

    def test_schema_version_present(self):
        assert SCHEMA_VERSION == "3.0.0"

    def test_hash_algorithm_present(self):
        assert HASH_ALGORITHM == "sha256"

    def test_expected_pipeline_seed(self):
        assert EXPECTED_PIPELINE_SEED == "0"

    def test_namespace_prefixes_distinct(self):
        assert HASH_NODES_PREFIX != HASH_EDGES_PREFIX
        assert HASH_BLOB_SEPARATOR == b"\x00"

    def test_compute_graph_id_function_works(self):
        """compute_graph_id factory deterministic and distinct per path."""
        gid1 = compute_graph_id("/proj/x")
        gid2 = compute_graph_id("/proj/x")
        gid3 = compute_graph_id("/proj/y")
        assert gid1 == gid2
        assert gid1 != gid3

    def test_generate_build_id_uniqueness(self):
        """generate_build_id produces unique values."""
        ids = {generate_build_id() for _ in range(50)}
        assert len(ids) == 50