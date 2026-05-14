"""
resolution_debug.json v2 — debug artifact contract.

Schema is versioned from day 1. Any field addition or semantic
change to existing fields requires SCHEMA_VERSION bump.
"""

from __future__ import annotations
import json
import uuid
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .telemetry import ResolutionTelemetry


SCHEMA_VERSION = "2.7.0"


@dataclass(frozen=True)
class BuildMetadata:
    """Identifies a single pipeline run for diff/regression purposes."""
    build_id: str
    timestamp: str           # ISO 8601 UTC
    git_commit: Optional[str]

    @classmethod
    def create(cls, git_commit: Optional[str] = None) -> "BuildMetadata":
        return cls(
            build_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            git_commit=git_commit,
        )


@dataclass
class ResolutionDebugReport:
    """
    Top-level debug artifact. Serialized as resolution_debug.json.

    Backward-compat note: the previous propagation_debug.json is
    superseded by this. Migration step: rename the output file.
    """
    schema_version: str = SCHEMA_VERSION
    build: BuildMetadata = field(default_factory=BuildMetadata.create)
    telemetry: Dict[str, Any] = field(default_factory=dict)
    samples: Dict[str, Any] = field(default_factory=dict)
    resolutions: List[Dict[str, Any]] = field(default_factory=list)
    invariants_passed: bool = False
    invariant_violations: List[str] = field(default_factory=list)

    @classmethod
    def from_telemetry(
        cls,
        telemetry: ResolutionTelemetry,
        *,
        build: Optional[BuildMetadata] = None,
        invariants_passed: bool = False,
        invariant_violations: Optional[List[str]] = None,
    ) -> "ResolutionDebugReport":
        return cls(
            schema_version=SCHEMA_VERSION,
            build=build or BuildMetadata.create(),
            telemetry=telemetry.to_dict(),
            samples={
                "unknown_reason": telemetry.unknown_reason_samples,
            },
            resolutions=[],   # populated by resolver layer in PR 2/PR 3
            invariants_passed=invariants_passed,
            invariant_violations=invariant_violations or [],
        )

    def write(self, path: str | Path) -> None:
        path = Path(path)
        with path.open("w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "build": asdict(self.build),
            "telemetry": self.telemetry,
            "samples": self.samples,
            "resolutions": self.resolutions,
            "invariants_passed": self.invariants_passed,
            "invariant_violations": self.invariant_violations,
        }