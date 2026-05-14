import json
import pytest
from lynkmesh.semantic.contracts import (
    ResolutionTelemetry, ResolutionDebugReport,
    BuildMetadata, SCHEMA_VERSION, ConfidenceClass,
)


def test_schema_version_present():
    t = ResolutionTelemetry()
    r = ResolutionDebugReport.from_telemetry(t)
    d = r.to_dict()
    assert d["schema_version"] == SCHEMA_VERSION


def test_build_metadata_present():
    t = ResolutionTelemetry()
    r = ResolutionDebugReport.from_telemetry(t)
    d = r.to_dict()
    assert "build_id" in d["build"]
    assert "timestamp" in d["build"]
    assert "git_commit" in d["build"]


def test_serialization_round_trip(tmp_path):
    t = ResolutionTelemetry()
    t.record_attempt(ConfidenceClass.EXACT)
    t.record_hit(ConfidenceClass.EXACT)
    t.record_emission(ConfidenceClass.EXACT)

    r = ResolutionDebugReport.from_telemetry(
        t, invariants_passed=True
    )
    out = tmp_path / "resolution_debug.json"
    r.write(out)

    with out.open() as f:
        loaded = json.load(f)

    assert loaded["schema_version"] == SCHEMA_VERSION
    assert loaded["telemetry"]["emitted"]["exact"] == 1
    assert loaded["invariants_passed"] is True


def test_distinct_build_ids():
    a = BuildMetadata.create()
    b = BuildMetadata.create()
    assert a.build_id != b.build_id