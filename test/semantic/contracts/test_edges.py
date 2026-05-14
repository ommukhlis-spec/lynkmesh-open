import pytest
from lynkmesh.semantic.contracts import (
    CallEdge, EdgeType, ConfidenceClass,
    SourceLocation, RejectReason,
)

LOC = SourceLocation(file="x.php", line=10, col=5)


def test_emitted_edge_has_no_reject_reason():
    e = CallEdge(
        source_id="A", target_id="B",
        edge_type=EdgeType.CALLS,
        confidence=ConfidenceClass.EXACT,
        site=LOC,
    )
    assert e.is_emitted is True


def test_rejected_edge_carries_reason():
    e = CallEdge(
        source_id="A", target_id="B",
        edge_type=EdgeType.CALLS,
        confidence=ConfidenceClass.PROPAGATED,
        site=LOC,
        reject_reason=RejectReason.NOT_YET_IMPLEMENTED,
    )
    assert e.is_emitted is False


def test_edge_type_closed_vocabulary():
    expected = {
        "CALLS", "INSTANTIATES", "IMPLEMENTS", "EXTENDS", "USES",
        "RETURNS", "THROWS", "DISPATCHES", "ROUTES_TO",
        "READS", "WRITES", "CONTAINS",
    }
    assert {e.name for e in EdgeType} == expected