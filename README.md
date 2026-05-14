# LynkMesh Open Core

LynkMesh is an open-core code graph foundation for building deterministic, queryable snapshots of legacy codebases.

The open-core package focuses on the foundations: graph construction, stable graph identity, canonical serialization, local graph caching, graph snapshot diffing, and an incremental pipeline report API that can be consumed by future CLI, editor, or integration layers.

## What this repository provides

- Deterministic graph identity with `GraphVersion`
- Canonical JSON-safe graph serialization with `GraphSerializer`
- Local filesystem graph snapshot caching with `GraphCache`
- Deterministic graph snapshot diffs with `IncrementalDiffEngine`
- A consumer-facing `IncrementalPipeline` summary/report API
- Semantic contract primitives for resolver confidence, provenance, telemetry, and debug exports
- Public unit and contract tests for the open-core boundary

## Current scope

LynkMesh currently emphasizes deterministic static graph construction and snapshot comparison.

For dynamic runtime behavior, framework magic, reflection-heavy code, and dependency injection patterns, results may be incomplete. Treat LynkMesh output as developer-assistance signals rather than absolute ground truth.

## Open-core versus premium boundary

The open-core edition provides the deterministic graph foundation.

Advanced impact analysis, AI-assisted reasoning, production integration tools, team workflows, commercial automation, and future partial-rebuild systems are expected to live in premium or private packages.

## Installation for development

From the repository root:

```bash
python -m pip install -e .[dev]
```

Or run the public tests directly from the repository root:

```bash
python -m pytest test/unit/core/test_graph_version.py -v
python -m pytest test/unit/core/test_graph_serializer.py -v
python -m pytest test/unit/pipeline/test_incremental_pipeline_schema.py -v
python -m pytest test/semantic/contracts/ -v
```

## Determinism requirement

For deterministic graph builds, set:

```bash
PYTHONHASHSEED=0
```

On Windows CMD:

```cmd
set PYTHONHASHSEED=0
```

## Legacy parser bridge

Some current PHP ingestion paths can use an optional legacy parser runtime via environment variables:

```bash
LYNKMESH_LEGACY_ROOT=/path/to/legacy_runtime
LYNKMESH_PARSER_PATH=/path/to/parser.php
```

The legacy runtime itself is not included in this open-core repository. Native parser and ingestion improvements are expected to evolve over time.

## Core modules

```text
lynkmesh/core/graph_core.py          Core graph container
lynkmesh/core/graph_version.py       Stable graph identity and content hash
lynkmesh/core/graph_serializer.py    Canonical graph serialization
lynkmesh/core/graph_cache.py         Local graph snapshot cache
lynkmesh/core/incremental_diff.py    Graph snapshot diff engine
lynkmesh/pipeline/orchestrator.py    Full graph build orchestration
lynkmesh/pipeline/incremental_pipeline.py
                                     Full-build + cache + diff report layer
```

## IncrementalPipeline API

`IncrementalPipeline` currently performs a full graph build, serializes the graph, optionally saves it to local cache, and compares it with a prior cached snapshot when available.

It does not yet perform partial rebuilds or file watching.

See:

```text
lynkmesh/pipeline/INCREMENTAL_PIPELINE_API.md
```

## Minimal example

```python
from lynkmesh.pipeline.incremental_pipeline import IncrementalPipeline

pipeline = IncrementalPipeline(cache_dir=".lynkmesh-cache")
report = pipeline.run("/path/to/project")

print(report.summary_line())
print(report.to_summary_dict())
```

## Limitations

- Static graph construction is not equivalent to runtime tracing.
- Framework-specific behavior may require additional modeling.
- Reflection, dynamic dispatch, and dependency injection can reduce call-graph precision.
- Partial rebuild is not implemented in the open-core foundation yet.
- Production integrations are outside this repository's current scope.

## License

Apache License 2.0. See `LICENSE`.
