"""
Resolution telemetry — compiler-pass diagnostics.

Per-run scope. Reset every pipeline build. No persistence.

Invariants are HARD assertions: pipeline halts on violation.
"""

from __future__ import annotations
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

from .confidence import ConfidenceClass
from .resolution import FailureReason, RejectReason


class InvariantViolation(AssertionError):
    """Raised when telemetry accounting fails. Never caught silently."""
    pass


@dataclass
class ResolutionTelemetry:
    """
    Three-axis telemetry: attempts, hits, emitted.
    Plus: rejected (subclass of hits), no_resolution (subclass of attempts).

    Accounting model:

        attempts[C] = hits[C] + (no_resolution where attempted_class == C)
        hits[C]     = emitted[C] + (rejected where confidence_class == C)
        sum(emitted.*) == call_edges_added_this_run

    The third invariant is delta-based (per-run delta, not total graph),
    forward-compatible with incremental graph updates in Phase 3.
    """

    MAX_UNKNOWN_SAMPLES: int = 50

    attempts:      Counter = field(default_factory=Counter)  # ConfidenceClass -> int
    hits:          Counter = field(default_factory=Counter)  # ConfidenceClass -> int
    emitted:       Counter = field(default_factory=Counter)  # ConfidenceClass -> int
    rejected:      Counter = field(default_factory=Counter)  # (ConfidenceClass, RejectReason) -> int
    no_resolution: Counter = field(default_factory=Counter)  # (ConfidenceClass, FailureReason) -> int
    unknown_reason_samples: List[Dict[str, Any]] = field(default_factory=list)

    # ---- recording API ----------------------------------------------------

    def record_attempt(self, confidence: ConfidenceClass) -> None:
        self.attempts[confidence] += 1

    def record_hit(self, confidence: ConfidenceClass) -> None:
        self.hits[confidence] += 1

    def record_emission(self, confidence: ConfidenceClass) -> None:
        self.emitted[confidence] += 1

    def record_rejection(
        self, confidence: ConfidenceClass, reason: RejectReason
    ) -> None:
        self.rejected[(confidence, reason)] += 1

    def record_no_resolution(
        self,
        attempted_confidence: ConfidenceClass,
        reason: FailureReason,
        sample: Dict[str, Any] | None = None,
    ) -> None:
        self.no_resolution[(attempted_confidence, reason)] += 1
        if reason == FailureReason.UNKNOWN_REASON and sample is not None:
            if len(self.unknown_reason_samples) < self.MAX_UNKNOWN_SAMPLES:
                self.unknown_reason_samples.append(sample)

    # ---- invariants -------------------------------------------------------

    def assert_invariants(self, *, call_edges_added_this_run: int) -> None:
        """
        Hard-fail if accounting inconsistent. Call once at end of resolver pass.

        `call_edges_added_this_run` MUST come from the graph builder's
        actual emission count, not from this telemetry's `emitted`.
        That's the whole point of cross-checking.
        """
        for c in ConfidenceClass:
            attempts = self.attempts[c]
            hits = self.hits[c]
            no_res_for_c = sum(
                v for (cc, _), v in self.no_resolution.items() if cc == c
            )
            emitted = self.emitted[c]
            rejected_for_c = sum(
                v for (cc, _), v in self.rejected.items() if cc == c
            )

            if attempts != hits + no_res_for_c:
                raise InvariantViolation(
                    f"[{c.value}] attempts({attempts}) != "
                    f"hits({hits}) + no_resolution({no_res_for_c})"
                )

            if hits != emitted + rejected_for_c:
                raise InvariantViolation(
                    f"[{c.value}] hits({hits}) != "
                    f"emitted({emitted}) + rejected({rejected_for_c})"
                )

        total_emitted = sum(self.emitted.values())
        if total_emitted != call_edges_added_this_run:
            raise InvariantViolation(
                f"global delta: sum(emitted)={total_emitted} != "
                f"call_edges_added_this_run={call_edges_added_this_run}"
            )

    # ---- serialization ----------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "attempts":      {c.value: n for c, n in self.attempts.items()},
            "hits":          {c.value: n for c, n in self.hits.items()},
            "emitted":       {c.value: n for c, n in self.emitted.items()},
            "rejected": [
                {"confidence": c.value, "reason": r.value, "count": n}
                for (c, r), n in self.rejected.items()
            ],
            "no_resolution": [
                {"confidence": c.value, "reason": r.value, "count": n}
                for (c, r), n in self.no_resolution.items()
            ],
            "unknown_reason_samples": list(self.unknown_reason_samples),
        }