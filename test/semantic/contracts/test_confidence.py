import pytest
from lynkmesh.semantic.contracts import ConfidenceClass, ConfidenceReport


def test_confidence_class_is_closed_enum():
    expected = {"EXACT", "PROPAGATED", "HEURISTIC",
                "FRAMEWORK", "EXTERNAL", "UNKNOWN"}
    assert {c.name for c in ConfidenceClass} == expected


def test_trust_rank_is_total_order():
    ranks = [c.trust_rank for c in ConfidenceClass]
    assert len(set(ranks)) == len(ranks), "trust ranks must be unique"


def test_confidence_report_rejects_out_of_range_score():
    with pytest.raises(ValueError):
        ConfidenceReport(score=1.5, factors={"x": 1.0})
    with pytest.raises(ValueError):
        ConfidenceReport(score=-0.1, factors={"x": 1.0})


def test_confidence_report_rejects_out_of_range_factor():
    with pytest.raises(ValueError):
        ConfidenceReport(score=0.5, factors={"x": 1.5})


def test_confidence_report_rejects_empty_factors():
    with pytest.raises(ValueError):
        ConfidenceReport(score=1.0, factors={})


def test_from_factors_multiplicative():
    r = ConfidenceReport.from_factors({"a": 0.5, "b": 0.5})
    assert r.score == 0.25


def test_factors_immutable():
    r = ConfidenceReport(score=0.5, factors={"x": 0.5})
    with pytest.raises(TypeError):
        r.factors["x"] = 0.9   # type: ignore[index]