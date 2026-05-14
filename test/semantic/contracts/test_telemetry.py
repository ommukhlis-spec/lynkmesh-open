import pytest
from lynkmesh.semantic.contracts import (
    ResolutionTelemetry, ConfidenceClass,
    FailureReason, RejectReason, InvariantViolation,
)


def test_clean_run_invariants_pass():
    t = ResolutionTelemetry()
    t.record_attempt(ConfidenceClass.EXACT)
    t.record_hit(ConfidenceClass.EXACT)
    t.record_emission(ConfidenceClass.EXACT)
    t.assert_invariants(call_edges_added_this_run=1)


def test_attempts_must_equal_hits_plus_no_resolution():
    t = ResolutionTelemetry()
    t.record_attempt(ConfidenceClass.PROPAGATED)
    # forgot to record hit OR no_resolution
    with pytest.raises(InvariantViolation):
        t.assert_invariants(call_edges_added_this_run=0)


def test_hits_must_equal_emitted_plus_rejected():
    t = ResolutionTelemetry()
    t.record_attempt(ConfidenceClass.PROPAGATED)
    t.record_hit(ConfidenceClass.PROPAGATED)
    # neither emitted nor rejected
    with pytest.raises(InvariantViolation):
        t.assert_invariants(call_edges_added_this_run=0)


def test_global_delta_must_match_graph_builder():
    t = ResolutionTelemetry()
    t.record_attempt(ConfidenceClass.EXACT)
    t.record_hit(ConfidenceClass.EXACT)
    t.record_emission(ConfidenceClass.EXACT)
    # graph builder reports 0 edges added — mismatch
    with pytest.raises(InvariantViolation):
        t.assert_invariants(call_edges_added_this_run=0)


def test_simulate_F1_bug_is_caught():
    """
    The bug we want this telemetry to expose: propagation hits
    but emits zero edges.
    """
    t = ResolutionTelemetry()
    for _ in range(723):
        t.record_attempt(ConfidenceClass.PROPAGATED)
        t.record_hit(ConfidenceClass.PROPAGATED)
        # no emission, no rejection — silent drop
    with pytest.raises(InvariantViolation) as exc:
        t.assert_invariants(call_edges_added_this_run=0)
    assert "propagated" in str(exc.value)


def test_unknown_reason_sample_bucket_bounded():
    t = ResolutionTelemetry()
    t.MAX_UNKNOWN_SAMPLES = 3
    for i in range(10):
        t.record_attempt(ConfidenceClass.UNKNOWN)
        t.record_no_resolution(
            ConfidenceClass.UNKNOWN,
            FailureReason.UNKNOWN_REASON,
            sample={"i": i},
        )
    assert len(t.unknown_reason_samples) == 3


def test_rejected_propagated_with_not_yet_implemented_validates():
    """
    PR 3 transitional state: propagation hits but every emission is
    rejected with NOT_YET_IMPLEMENTED. Invariants must still pass.
    """
    t = ResolutionTelemetry()
    for _ in range(723):
        t.record_attempt(ConfidenceClass.PROPAGATED)
        t.record_hit(ConfidenceClass.PROPAGATED)
        t.record_rejection(
            ConfidenceClass.PROPAGATED,
            RejectReason.NOT_YET_IMPLEMENTED,
        )
    t.assert_invariants(call_edges_added_this_run=0)