import pytest
from lynkmesh.semantic.contracts import (
    ConfidenceClass, ResolutionResult, ResolutionOutcome,
    FailureReason, RejectReason,
    SourceLocation, ProvenanceChain,
)

LOC = SourceLocation(file="x.php", line=1, col=1)


def test_resolved_requires_callee():
    with pytest.raises(ValueError):
        ResolutionResult(
            caller_id="A", site=LOC, confidence=ConfidenceClass.EXACT,
            outcome=ResolutionOutcome.RESOLVED,
        )


def test_resolved_forbids_failure_reason():
    with pytest.raises(ValueError):
        ResolutionResult(
            caller_id="A", site=LOC, confidence=ConfidenceClass.EXACT,
            outcome=ResolutionOutcome.RESOLVED,
            callee_id="B",
            failure_reason=FailureReason.NO_OBJECT,
        )


def test_rejected_requires_reject_reason():
    with pytest.raises(ValueError):
        ResolutionResult(
            caller_id="A", site=LOC, confidence=ConfidenceClass.PROPAGATED,
            outcome=ResolutionOutcome.REJECTED,
            callee_id="B",
        )


def test_no_target_requires_failure_reason():
    with pytest.raises(ValueError):
        ResolutionResult(
            caller_id="A", site=LOC, confidence=ConfidenceClass.UNKNOWN,
            outcome=ResolutionOutcome.NO_TARGET,
        )


def test_no_target_forbids_callee():
    with pytest.raises(ValueError):
        ResolutionResult(
            caller_id="A", site=LOC, confidence=ConfidenceClass.UNKNOWN,
            outcome=ResolutionOutcome.NO_TARGET,
            callee_id="B",
            failure_reason=FailureReason.NO_OBJECT,
        )


def test_failure_reason_exhaustive_coverage():
    """Every FailureReason must be reachable by at least one constructor."""
    for fr in FailureReason:
        r = ResolutionResult(
            caller_id="A", site=LOC, confidence=ConfidenceClass.UNKNOWN,
            outcome=ResolutionOutcome.NO_TARGET,
            failure_reason=fr,
        )
        assert r.failure_reason is fr


def test_reject_reason_exhaustive_coverage():
    for rr in RejectReason:
        r = ResolutionResult(
            caller_id="A", site=LOC, confidence=ConfidenceClass.PROPAGATED,
            outcome=ResolutionOutcome.REJECTED,
            callee_id="B",
            reject_reason=rr,
        )
        assert r.reject_reason is rr