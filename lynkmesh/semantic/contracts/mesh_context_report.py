"""
mesh_context_report.json v0.1 — AI consumption protocol contract.

MeshContext Report separates deterministic LynkMesh graph facts from LLM
interpretation. This artifact must not contain LLM inference.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional


MESH_CONTEXT_SCHEMA_VERSION = "0.1.0"
MESH_CONTEXT_REPORT_TYPE = "mesh_context_report"

_CONFIDENCE_CLASSES = (
    "EXACT",
    "PROPAGATED",
    "HEURISTIC",
    "FRAMEWORK",
    "EXTERNAL",
    "UNKNOWN",
)

_DETERMINISTIC_SECTION_KEYS = (
    "graph_facts",
    "languages",
    "entrypoints",
    "hotspots",
    "risk_candidates",
    "dependency_summary",
    "limitations",
    "llm_instructions",
)

_WINDOWS_ABSOLUTE_PATH_RE = re.compile(r"[A-Za-z]:[\\/][^\s\"']+")
_POSIX_ABSOLUTE_PATH_RE = re.compile(r"(^|[\s\"'])/[A-Za-z0-9_.-]+/")
_HOME_SEGMENT_RE = re.compile(r"[\\/](Users|home)[\\/][^\\/]+[\\/]")


@dataclass(frozen=True)
class MeshProjectMetadata:
    """Sanitized project metadata for AI consumption."""
    display_name: str
    primary_language: str
    languages: Dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class MeshBuildMetadata:
    """Build and graph identity metadata."""
    build_id: str
    graph_id: str
    content_hash: str
    git_commit: Optional[str]
    pipeline_schema_version: Optional[str]
    serializer_schema_version: str
    parser_source: Optional[str]
    parser_executor_mode: Optional[str]
    build_duration_seconds: Optional[float] = None


@dataclass(frozen=True)
class MeshProvenance:
    """Machine-checkable provenance for the report."""
    generator: str
    generator_version: str
    graph_content_hash: str
    is_deterministic: bool
    contains_llm_inference: bool
    sections: Dict[str, Dict[str, Any]] = field(default_factory=dict)


@dataclass
class MeshContextReport:
    """
    Top-level MeshContext Report artifact.

    This report contains deterministic facts and deterministic candidates only.
    Human-readable architecture interpretation belongs in a separate LLM artifact.
    """
    schema_version: str = MESH_CONTEXT_SCHEMA_VERSION
    report_type: str = MESH_CONTEXT_REPORT_TYPE
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    project: MeshProjectMetadata = field(
        default_factory=lambda: MeshProjectMetadata(
            display_name="unknown-project",
            primary_language="unknown",
            languages={},
        )
    )
    build: MeshBuildMetadata = field(
        default_factory=lambda: MeshBuildMetadata(
            build_id="",
            graph_id="",
            content_hash="",
            git_commit=None,
            pipeline_schema_version=None,
            serializer_schema_version="",
            parser_source=None,
            parser_executor_mode=None,
            build_duration_seconds=None,
        )
    )
    graph_facts: Dict[str, Any] = field(default_factory=dict)
    languages: Dict[str, Any] = field(default_factory=dict)
    entrypoints: List[Dict[str, Any]] = field(default_factory=list)
    hotspots: List[Dict[str, Any]] = field(default_factory=list)
    risk_candidates: List[Dict[str, Any]] = field(default_factory=list)
    dependency_summary: Dict[str, Any] = field(default_factory=dict)
    limitations: List[str] = field(default_factory=list)
    llm_instructions: Dict[str, Any] = field(default_factory=dict)
    provenance: MeshProvenance = field(
        default_factory=lambda: MeshProvenance(
            generator="lynkmesh",
            generator_version="0.1.0",
            graph_content_hash="",
            is_deterministic=True,
            contains_llm_inference=False,
            sections={},
        )
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "report_type": self.report_type,
            "generated_at": self.generated_at,
            "project": asdict(self.project),
            "build": asdict(self.build),
            "graph_facts": self.graph_facts,
            "languages": self.languages,
            "entrypoints": self.entrypoints,
            "hotspots": self.hotspots,
            "risk_candidates": self.risk_candidates,
            "dependency_summary": self.dependency_summary,
            "limitations": self.limitations,
            "llm_instructions": self.llm_instructions,
            "provenance": asdict(self.provenance),
        }

    def deterministic_sections(self) -> Dict[str, Any]:
        payload = self.to_dict()
        return {key: payload[key] for key in _DETERMINISTIC_SECTION_KEYS}

    def write(self, path: str | Path) -> None:
        path = Path(path)
        with path.open("w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False, sort_keys=True)


def build_mesh_context_report(
    serialized_payload: Mapping[str, Any],
    *,
    project_display_name: Optional[str] = None,
    primary_language: Optional[str] = None,
    languages: Optional[Mapping[str, int]] = None,
    pipeline_schema_version: Optional[str] = None,
    parser_source: Optional[str] = None,
    parser_executor_mode: Optional[str] = None,
    build_duration_seconds: Optional[float] = None,
    generator_version: str = "4.3.1",
    generated_at: Optional[str] = None,
) -> MeshContextReport:
    """
    Build a MeshContext Report from an existing serialized graph payload.

    This is a pure projection layer. It must not mutate graph runtime state and
    must not include LLM inference.
    """
    version = _mapping(serialized_payload.get("version"))
    metadata = _mapping(version.get("metadata"))
    stats = _mapping(serialized_payload.get("stats"))
    nodes = _list_of_mappings(serialized_payload.get("nodes"))
    edges = _list_of_mappings(serialized_payload.get("edges"))

    content_hash = str(version.get("content_hash") or "")
    graph_id = str(metadata.get("graph_id") or "")
    build_id = str(metadata.get("build_id") or "")
    git_commit = metadata.get("git_commit")
    serializer_schema_version = str(serialized_payload.get("schema_version") or "")

    language_mix = _normalize_language_mix(languages)
    inferred_primary = primary_language or _primary_language_from_mix(language_mix)

    project = MeshProjectMetadata(
        display_name=_sanitize_display_name(project_display_name),
        primary_language=inferred_primary,
        languages=language_mix,
    )

    build = MeshBuildMetadata(
        build_id=build_id,
        graph_id=graph_id,
        content_hash=content_hash,
        git_commit=str(git_commit) if git_commit is not None else None,
        pipeline_schema_version=pipeline_schema_version,
        serializer_schema_version=serializer_schema_version,
        parser_source=parser_source,
        parser_executor_mode=parser_executor_mode,
        build_duration_seconds=build_duration_seconds,
    )

    graph_facts = {
        "node_count": _safe_int(stats.get("nodes"), default=len(nodes)),
        "edge_count": _safe_int(stats.get("edges"), default=len(edges)),
        "node_type_breakdown": _node_type_breakdown(stats, nodes),
        "edge_type_breakdown": _edge_type_breakdown(edges),
        "confidence_distribution": _confidence_distribution(edges),
    }

    languages_block = {
        "primary": inferred_primary,
        "supported": sorted(language_mix.keys()),
        "mix": language_mix,
    }

    dependency_summary = {
        "layers": [],
        "layer_edges": [],
        "cycles_detected": 0,
        "cross_layer_candidates": [],
    }

    limitations = [
        "Semantic analysis is limited to supported parser capabilities.",
        "Dynamic dispatch resolution may be incomplete.",
        "Heuristic and propagated facts should be down-weighted.",
        "Entrypoints, hotspots, and risk candidates are deterministic candidates, not validated conclusions.",
        "The report reflects source state at build time, not runtime execution.",
    ]

    llm_instructions = {
        "role": "Interpret deterministic facts; do not invent graph relationships.",
        "allowed_inferences": [
            "architecture narrative",
            "domain naming",
            "recommendations",
            "risk communication",
        ],
        "forbidden": [
            "inventing edges",
            "treating candidates as confirmed defects",
            "claiming runtime behavior from static graph facts",
        ],
        "confidence_policy": "Down-weight HEURISTIC and PROPAGATED facts.",
        "token_policy": "Reference compact node identifiers instead of restating large node lists.",
    }

    provenance = MeshProvenance(
        generator="lynkmesh",
        generator_version=generator_version,
        graph_content_hash=content_hash,
        is_deterministic=True,
        contains_llm_inference=False,
        sections={
            "graph_facts": {
                "engine": "graph_serializer",
                "deterministic": True,
            },
            "languages": {
                "engine": "mesh_context_projection",
                "deterministic": True,
            },
            "entrypoints": {
                "engine": "not_populated_v0_1",
                "deterministic": True,
            },
            "hotspots": {
                "engine": "not_populated_v0_1",
                "deterministic": True,
            },
            "risk_candidates": {
                "engine": "not_populated_v0_1",
                "deterministic": True,
            },
            "dependency_summary": {
                "engine": "conservative_empty_v0_1",
                "deterministic": True,
            },
        },
    )

    report = MeshContextReport(
        generated_at=generated_at or datetime.now(timezone.utc).isoformat(),
        project=project,
        build=build,
        graph_facts=graph_facts,
        languages=languages_block,
        entrypoints=[],
        hotspots=[],
        risk_candidates=[],
        dependency_summary=dependency_summary,
        limitations=limitations,
        llm_instructions=llm_instructions,
        provenance=provenance,
    )

    unsafe = find_unsafe_report_strings(report.to_dict())
    if unsafe:
        raise ValueError(f"MeshContextReport contains unsafe path-like strings: {unsafe[:3]}")

    return report


def find_unsafe_report_strings(value: Any) -> List[str]:
    """Return path-like unsafe strings found recursively in a report payload."""
    findings: List[str] = []

    def visit(item: Any, path: str) -> None:
        if isinstance(item, str):
            if _is_unsafe_string(item):
                findings.append(f"{path}: {item}")
            return
        if isinstance(item, Mapping):
            for key, child in item.items():
                visit(child, f"{path}.{key}")
            return
        if isinstance(item, list):
            for index, child in enumerate(item):
                visit(child, f"{path}[{index}]")

    visit(value, "$")
    return findings


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _list_of_mappings(value: Any) -> List[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _safe_int(value: Any, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_language_mix(languages: Optional[Mapping[str, int]]) -> Dict[str, int]:
    if not languages:
        return {}
    normalized: Dict[str, int] = {}
    for name, count in languages.items():
        key = str(name).strip().lower()
        if not key:
            continue
        normalized[key] = _safe_int(count)
    return dict(sorted(normalized.items()))


def _primary_language_from_mix(language_mix: Mapping[str, int]) -> str:
    if not language_mix:
        return "unknown"
    return max(sorted(language_mix), key=lambda key: language_mix[key])


def _sanitize_display_name(value: Optional[str]) -> str:
    text = str(value or "unknown-project").replace("\\", "/").strip()
    text = text.rstrip("/").split("/")[-1]
    text = re.sub(r"[^A-Za-z0-9_.-]+", "-", text).strip(".-")
    return text[:80] or "unknown-project"


def _node_type_breakdown(stats: Mapping[str, Any], nodes: List[Mapping[str, Any]]) -> Dict[str, int]:
    breakdown = {
        "file": _safe_int(stats.get("files")),
        "class": _safe_int(stats.get("classes")),
        "method": _safe_int(stats.get("methods")),
        "function": _safe_int(stats.get("functions")),
        "external": _safe_int(stats.get("external")),
    }

    if any(breakdown.values()):
        return breakdown

    counter: Counter[str] = Counter()
    for node in nodes:
        node_type = node.get("type") or node.get("node_type") or node.get("kind")
        if node_type:
            counter[str(node_type)] += 1

    return dict(sorted(counter.items()))


def _edge_type_breakdown(edges: List[Mapping[str, Any]]) -> Dict[str, int]:
    counter: Counter[str] = Counter()
    for edge in edges:
        edge_type = edge.get("type") or edge.get("edge_type") or edge.get("kind")
        if edge_type:
            counter[str(edge_type)] += 1
    return dict(sorted(counter.items()))


def _confidence_distribution(edges: List[Mapping[str, Any]]) -> Dict[str, int]:
    distribution = {name: 0 for name in _CONFIDENCE_CLASSES}
    for edge in edges:
        raw = edge.get("confidence") or edge.get("confidence_class")
        if raw is None:
            continue
        key = str(raw).upper()
        if key not in distribution:
            key = "UNKNOWN"
        distribution[key] += 1
    return distribution


def _is_unsafe_string(value: str) -> bool:
    if _WINDOWS_ABSOLUTE_PATH_RE.search(value):
        return True
    if _POSIX_ABSOLUTE_PATH_RE.search(value):
        return True
    if _HOME_SEGMENT_RE.search(value):
        return True
    return False