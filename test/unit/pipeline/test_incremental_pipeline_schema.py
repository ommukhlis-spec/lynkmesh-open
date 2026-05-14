# lynkmesh/test/unit/pipeline/test_incremental_pipeline_schema.py
"""
Stage 3.5.0 — Frozen schema contract test for IncrementalRunReport.

This test IS the public ABI contract. It must fail loudly on any
unintended schema change. Future stages adding new fields must extend
this file; never silently relax assertions.

This is the only PUBLIC test file added in Stage 3.5.0 because the
schema is the public API for downstream consumers (CLI, MCP, external).

Test organization:
    Section 1: Top-level keys frozen
    Section 2: current block frozen
    Section 3: cache block frozen
    Section 4: comparison block frozen
    Section 5: derived block frozen
    Section 6: result_status values frozen
    Section 7: cache.status values frozen
    Section 8: comparison.status values frozen
    Section 9: to_summary_dict shape frozen
    Section 10: schema version constants frozen
    Section 11: JSON safety of all helpers
"""

from __future__ import annotations

import json
from typing import Any, Dict

import pytest

from lynkmesh.core.graph_core import GraphCore
from lynkmesh.core.graph_version import JSON_SERIALIZATION_OPTIONS
from lynkmesh.pipeline.incremental_pipeline import (
    CACHE_STATUS_DEDUPLICATED,
    CACHE_STATUS_DISABLED,
    CACHE_STATUS_SAVED,
    CACHE_STATUS_SAVE_SKIPPED,
    COMPARISON_STATUS_COMPARED,
    COMPARISON_STATUS_DISABLED,
    COMPARISON_STATUS_NO_PRIOR,
    COMPARISON_STATUS_PRIOR_CORRUPT,
    IncrementalPipeline,
    IncrementalRunReport,
    PIPELINE_SCHEMA_VERSION,
    RESULT_STATUS_SUCCESS,
)


# =============================================================================
# Synthetic fakes (no real pipeline needed for contract tests)
# =============================================================================

def _build_finalized_graph() -> GraphCore:
    g = GraphCore()
    cls_id = g.add_node(
        node_type="class", name="App\\Foo", qualified_name="App\\Foo",
        file_path="src/Foo.php", layer="service",
        extra={"extends": "Base"},
    )
    m_id = g.add_node(
        node_type="method", name="bar", qualified_name="App\\Foo::bar",
        file_path="src/Foo.php", layer="service",
        extra={"class": "App\\Foo", "visibility": "public"},
    )
    g.add_edge(cls_id, m_id, "contains", semantic="structural_contains")
    g._assign_initial_metadata(project_path="/proj/schema_test")
    g._finalize_content_hash()
    return g


class _FakeOrchestrator:
    def __init__(self, graph_or_factory):
        if callable(graph_or_factory) and not isinstance(graph_or_factory, GraphCore):
            self._factory = graph_or_factory
        else:
            self._factory = lambda: graph_or_factory

    def run(self, project_path: str) -> GraphCore:
        return self._factory()


def _make_first_run_report(tmp_path) -> IncrementalRunReport:
    graph = _build_finalized_graph()
    pipeline = IncrementalPipeline(
        cache_dir=tmp_path,
        orchestrator=_FakeOrchestrator(graph),
    )
    return pipeline.run("/proj/schema_test")


def _make_second_run_report(tmp_path) -> IncrementalRunReport:
    pipeline = IncrementalPipeline(
        cache_dir=tmp_path,
        orchestrator_factory=lambda: _FakeOrchestrator(_build_finalized_graph()),
    )
    pipeline.run("/proj/schema_test")
    return pipeline.run("/proj/schema_test")


def _make_no_cache_report() -> IncrementalRunReport:
    graph = _build_finalized_graph()
    pipeline = IncrementalPipeline(orchestrator=_FakeOrchestrator(graph))
    return pipeline.run("/proj/schema_test")


# =============================================================================
# SECTION 1 — Top-level keys frozen
# =============================================================================

EXPECTED_TOP_LEVEL_KEYS = frozenset({
    "pipeline_schema_version",
    "result_status",
    "completed_at",
    "project_path",
    "current",
    "cache",
    "comparison",
    "derived",
    "warnings",
})


class TestTopLevelKeysFrozen:

    def test_first_run_top_level_keys_exact(self, tmp_path):
        d = _make_first_run_report(tmp_path).to_dict()
        assert set(d.keys()) == EXPECTED_TOP_LEVEL_KEYS

    def test_second_run_top_level_keys_exact(self, tmp_path):
        d = _make_second_run_report(tmp_path).to_dict()
        assert set(d.keys()) == EXPECTED_TOP_LEVEL_KEYS

    def test_no_cache_run_top_level_keys_exact(self):
        d = _make_no_cache_report().to_dict()
        assert set(d.keys()) == EXPECTED_TOP_LEVEL_KEYS


# =============================================================================
# SECTION 2 — current block frozen
# =============================================================================

EXPECTED_CURRENT_KEYS = frozenset({
    "graph_id", "build_id", "content_hash", "stats",
})

EXPECTED_STATS_KEYS = frozenset({
    "nodes", "edges", "files", "classes", "methods", "functions", "external",
})


class TestCurrentBlockFrozen:

    def test_current_block_keys_exact(self, tmp_path):
        d = _make_first_run_report(tmp_path).to_dict()
        assert set(d["current"].keys()) == EXPECTED_CURRENT_KEYS

    def test_current_stats_keys_exact(self, tmp_path):
        d = _make_first_run_report(tmp_path).to_dict()
        assert set(d["current"]["stats"].keys()) == EXPECTED_STATS_KEYS

    def test_current_content_hash_is_64_char_hex(self, tmp_path):
        d = _make_first_run_report(tmp_path).to_dict()
        ch = d["current"]["content_hash"]
        assert isinstance(ch, str)
        assert len(ch) == 64
        int(ch, 16)

    def test_current_build_id_non_empty_string(self, tmp_path):
        d = _make_first_run_report(tmp_path).to_dict()
        assert isinstance(d["current"]["build_id"], str)
        assert d["current"]["build_id"]

    def test_current_graph_id_non_empty_string(self, tmp_path):
        d = _make_first_run_report(tmp_path).to_dict()
        assert isinstance(d["current"]["graph_id"], str)
        assert d["current"]["graph_id"]


# =============================================================================
# SECTION 3 — cache block frozen
# =============================================================================

EXPECTED_CACHE_KEYS = frozenset({
    "enabled", "status", "cache_dir", "content_path",
})


class TestCacheBlockFrozen:

    def test_cache_block_keys_exact_with_cache(self, tmp_path):
        d = _make_first_run_report(tmp_path).to_dict()
        assert set(d["cache"].keys()) == EXPECTED_CACHE_KEYS

    def test_cache_block_keys_exact_no_cache(self):
        d = _make_no_cache_report().to_dict()
        assert set(d["cache"].keys()) == EXPECTED_CACHE_KEYS

    def test_cache_enabled_is_bool(self, tmp_path):
        d = _make_first_run_report(tmp_path).to_dict()
        assert isinstance(d["cache"]["enabled"], bool)
        assert d["cache"]["enabled"] is True

    def test_no_cache_enabled_false(self):
        d = _make_no_cache_report().to_dict()
        assert d["cache"]["enabled"] is False

    def test_no_cache_cache_dir_null(self):
        d = _make_no_cache_report().to_dict()
        assert d["cache"]["cache_dir"] is None
        assert d["cache"]["content_path"] is None


# =============================================================================
# SECTION 4 — comparison block frozen
# =============================================================================

EXPECTED_COMPARISON_KEYS = frozenset({
    "status", "prior_content_hash", "prior_build_id",
    "diff_summary", "diff_warnings",
})


class TestComparisonBlockFrozen:

    def test_comparison_block_keys_first_run(self, tmp_path):
        d = _make_first_run_report(tmp_path).to_dict()
        assert set(d["comparison"].keys()) == EXPECTED_COMPARISON_KEYS

    def test_comparison_block_keys_second_run(self, tmp_path):
        d = _make_second_run_report(tmp_path).to_dict()
        assert set(d["comparison"].keys()) == EXPECTED_COMPARISON_KEYS

    def test_comparison_block_keys_no_cache(self):
        d = _make_no_cache_report().to_dict()
        assert set(d["comparison"].keys()) == EXPECTED_COMPARISON_KEYS

    def test_first_run_diff_summary_null(self, tmp_path):
        d = _make_first_run_report(tmp_path).to_dict()
        assert d["comparison"]["diff_summary"] is None
        assert d["comparison"]["diff_warnings"] is None

    def test_second_run_diff_summary_dict(self, tmp_path):
        d = _make_second_run_report(tmp_path).to_dict()
        assert isinstance(d["comparison"]["diff_summary"], dict)


# =============================================================================
# SECTION 5 — derived block frozen
# =============================================================================

EXPECTED_DERIVED_KEYS = frozenset({
    "has_changes", "change_counts", "compared_against_explicit_hash",
})

EXPECTED_CHANGE_COUNTS_KEYS = frozenset({
    "nodes_added", "nodes_removed", "nodes_changed",
    "edges_added", "edges_removed", "edges_changed",
})


class TestDerivedBlockFrozen:

    def test_derived_block_keys_exact_first_run(self, tmp_path):
        d = _make_first_run_report(tmp_path).to_dict()
        assert set(d["derived"].keys()) == EXPECTED_DERIVED_KEYS

    def test_derived_block_keys_exact_second_run(self, tmp_path):
        d = _make_second_run_report(tmp_path).to_dict()
        assert set(d["derived"].keys()) == EXPECTED_DERIVED_KEYS

    def test_derived_block_keys_exact_no_cache(self):
        d = _make_no_cache_report().to_dict()
        assert set(d["derived"].keys()) == EXPECTED_DERIVED_KEYS

    def test_change_counts_keys_exact(self, tmp_path):
        d = _make_first_run_report(tmp_path).to_dict()
        assert set(d["derived"]["change_counts"].keys()) == EXPECTED_CHANGE_COUNTS_KEYS

    def test_change_counts_all_int(self, tmp_path):
        d = _make_second_run_report(tmp_path).to_dict()
        for v in d["derived"]["change_counts"].values():
            assert isinstance(v, int)

    def test_first_run_has_changes_false(self, tmp_path):
        d = _make_first_run_report(tmp_path).to_dict()
        assert d["derived"]["has_changes"] is False

    def test_second_run_identical_has_changes_false(self, tmp_path):
        d = _make_second_run_report(tmp_path).to_dict()
        assert d["derived"]["has_changes"] is False

    def test_compared_against_explicit_hash_default_false(self, tmp_path):
        d = _make_first_run_report(tmp_path).to_dict()
        assert d["derived"]["compared_against_explicit_hash"] is False


# =============================================================================
# SECTION 6 — result_status values frozen
# =============================================================================

class TestResultStatusFrozen:

    def test_result_status_constant_value(self):
        assert RESULT_STATUS_SUCCESS == "success"

    def test_result_status_in_report(self, tmp_path):
        d = _make_first_run_report(tmp_path).to_dict()
        assert d["result_status"] == "success"

    def test_result_status_no_cache(self):
        d = _make_no_cache_report().to_dict()
        assert d["result_status"] == "success"


# =============================================================================
# SECTION 7 — cache.status values frozen
# =============================================================================

EXPECTED_CACHE_STATUS_VALUES = frozenset({
    "saved", "deduplicated", "disabled", "save_skipped",
})


class TestCacheStatusFrozen:

    def test_cache_status_constants(self):
        assert CACHE_STATUS_SAVED == "saved"
        assert CACHE_STATUS_DEDUPLICATED == "deduplicated"
        assert CACHE_STATUS_DISABLED == "disabled"
        assert CACHE_STATUS_SAVE_SKIPPED == "save_skipped"

    def test_cache_status_constants_distinct(self):
        constants = {
            CACHE_STATUS_SAVED, CACHE_STATUS_DEDUPLICATED,
            CACHE_STATUS_DISABLED, CACHE_STATUS_SAVE_SKIPPED,
        }
        assert constants == EXPECTED_CACHE_STATUS_VALUES

    def test_first_run_status_saved(self, tmp_path):
        d = _make_first_run_report(tmp_path).to_dict()
        assert d["cache"]["status"] == "saved"

    def test_second_run_status_deduplicated(self, tmp_path):
        d = _make_second_run_report(tmp_path).to_dict()
        assert d["cache"]["status"] == "deduplicated"

    def test_no_cache_status_disabled(self):
        d = _make_no_cache_report().to_dict()
        assert d["cache"]["status"] == "disabled"


# =============================================================================
# SECTION 8 — comparison.status values frozen
# =============================================================================

EXPECTED_COMPARISON_STATUS_VALUES = frozenset({
    "no_prior", "prior_corrupt", "compared", "comparison_disabled",
})


class TestComparisonStatusFrozen:

    def test_comparison_status_constants(self):
        assert COMPARISON_STATUS_NO_PRIOR == "no_prior"
        assert COMPARISON_STATUS_PRIOR_CORRUPT == "prior_corrupt"
        assert COMPARISON_STATUS_COMPARED == "compared"
        assert COMPARISON_STATUS_DISABLED == "comparison_disabled"

    def test_comparison_status_constants_distinct(self):
        constants = {
            COMPARISON_STATUS_NO_PRIOR, COMPARISON_STATUS_PRIOR_CORRUPT,
            COMPARISON_STATUS_COMPARED, COMPARISON_STATUS_DISABLED,
        }
        assert constants == EXPECTED_COMPARISON_STATUS_VALUES

    def test_first_run_comparison_no_prior(self, tmp_path):
        d = _make_first_run_report(tmp_path).to_dict()
        assert d["comparison"]["status"] == "no_prior"

    def test_second_run_comparison_compared(self, tmp_path):
        d = _make_second_run_report(tmp_path).to_dict()
        assert d["comparison"]["status"] == "compared"

    def test_no_cache_comparison_disabled(self):
        d = _make_no_cache_report().to_dict()
        assert d["comparison"]["status"] == "comparison_disabled"


# =============================================================================
# SECTION 9 — to_summary_dict shape frozen
# =============================================================================

EXPECTED_SUMMARY_DICT_KEYS = frozenset({
    "pipeline_schema_version", "result_status",
    "content_hash", "graph_id", "build_id",
    "stats", "cache_status", "comparison_status",
    "has_changes", "change_counts",
    "compared_against_explicit_hash", "prior_content_hash",
})


class TestSummaryDictFrozen:

    def test_summary_dict_keys_exact_first_run(self, tmp_path):
        d = _make_first_run_report(tmp_path).to_summary_dict()
        assert set(d.keys()) == EXPECTED_SUMMARY_DICT_KEYS

    def test_summary_dict_keys_exact_second_run(self, tmp_path):
        d = _make_second_run_report(tmp_path).to_summary_dict()
        assert set(d.keys()) == EXPECTED_SUMMARY_DICT_KEYS

    def test_summary_dict_keys_exact_no_cache(self):
        d = _make_no_cache_report().to_summary_dict()
        assert set(d.keys()) == EXPECTED_SUMMARY_DICT_KEYS

    def test_summary_dict_stats_keys(self, tmp_path):
        d = _make_first_run_report(tmp_path).to_summary_dict()
        assert set(d["stats"].keys()) == EXPECTED_STATS_KEYS

    def test_summary_dict_change_counts_keys(self, tmp_path):
        d = _make_second_run_report(tmp_path).to_summary_dict()
        assert set(d["change_counts"].keys()) == EXPECTED_CHANGE_COUNTS_KEYS

    def test_summary_dict_json_serializable(self, tmp_path):
        d = _make_first_run_report(tmp_path).to_summary_dict()
        s = json.dumps(d, **JSON_SERIALIZATION_OPTIONS)
        reparsed = json.loads(s)
        assert reparsed == d


# =============================================================================
# SECTION 10 — Schema version constants frozen
# =============================================================================

class TestSchemaVersionFrozen:

    def test_pipeline_schema_version(self):
        assert PIPELINE_SCHEMA_VERSION == "3.4.0"

    def test_pipeline_schema_version_in_full_report(self, tmp_path):
        d = _make_first_run_report(tmp_path).to_dict()
        assert d["pipeline_schema_version"] == "3.4.0"

    def test_pipeline_schema_version_in_summary(self, tmp_path):
        d = _make_first_run_report(tmp_path).to_summary_dict()
        assert d["pipeline_schema_version"] == "3.4.0"


# =============================================================================
# SECTION 11 — JSON safety of all helpers
# =============================================================================

class TestJsonSafety:

    def test_full_to_dict_json_round_trip(self, tmp_path):
        d = _make_second_run_report(tmp_path).to_dict()
        s = json.dumps(d, **JSON_SERIALIZATION_OPTIONS)
        reparsed = json.loads(s)
        assert reparsed == d

    def test_to_dict_with_full_diff_json_round_trip(self, tmp_path):
        d = _make_second_run_report(tmp_path).to_dict(include_full_diff=True)
        s = json.dumps(d, **JSON_SERIALIZATION_OPTIONS)
        reparsed = json.loads(s)
        assert reparsed == d

    def test_summary_line_returns_string(self, tmp_path):
        line = _make_first_run_report(tmp_path).summary_line()
        assert isinstance(line, str)
        assert len(line) > 0

    def test_summary_line_no_cache(self):
        line = _make_no_cache_report().summary_line()
        assert "cache disabled" in line

    def test_summary_line_first_build(self, tmp_path):
        line = _make_first_run_report(tmp_path).summary_line()
        assert "first build" in line

    def test_summary_line_identical(self, tmp_path):
        line = _make_second_run_report(tmp_path).summary_line()
        assert "identical" in line