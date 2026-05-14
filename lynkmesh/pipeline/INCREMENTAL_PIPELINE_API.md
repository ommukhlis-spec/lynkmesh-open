# IncrementalPipeline API — Frozen Contract (Stage 3.5.0)

Stage 3.5.0 freezes the consumer-facing API of `IncrementalPipeline` and
`IncrementalRunReport`. This document is the reference for CLI, MCP, and
external tooling. The schema described here is enforced by the contract
test at `lynkmesh/test/unit/pipeline/test_incremental_pipeline_schema.py`.

Any change to the structure described here is a breaking change requiring
a `pipeline_schema_version` bump.

## Construction

```python
from lynkmesh.pipeline.incremental_pipeline import IncrementalPipeline

# No-cache mode
pipeline = IncrementalPipeline()

# With cache
pipeline = IncrementalPipeline(cache_dir="/var/lib/lynkmesh/cache")

# Injectable orchestrator
pipeline = IncrementalPipeline(orchestrator=my_orchestrator)
pipeline = IncrementalPipeline(orchestrator_factory=lambda: Orchestrator())
```

## run() Signature

```python
report = pipeline.run(
    project_path: str,
    *,
    compare_against_content_hash: Optional[str] = None,
    skip_cache_save: bool = False,
) -> IncrementalRunReport
```

## Report Consumption — Three Tiers

### Tier 1 — Human-readable
```python
print(report.summary_line())
# 🆕 first build (1108n/2400e) build=abc12345
# ✅ identical (1108n/2400e) build=abc12345 prior=abc12345
# ✏️  changed: +2/-1/~3n +5/-0/~1e build=def67890 prior=abc12345
```

### Tier 2 — Minimal JSON (recommended for CLI/MCP)
```python
report.to_summary_dict()
```
Returns:
```json
{
  "pipeline_schema_version": "3.4.0",
  "result_status": "success",
  "content_hash": "<hex>",
  "graph_id": "<uuid>",
  "build_id": "<uuid>",
  "stats": {"nodes": 1108, "edges": 2400, ...},
  "cache_status": "saved",
  "comparison_status": "no_prior",
  "has_changes": false,
  "change_counts": {
    "nodes_added": 0, "nodes_removed": 0, "nodes_changed": 0,
    "edges_added": 0, "edges_removed": 0, "edges_changed": 0
  },
  "compared_against_explicit_hash": false,
  "prior_content_hash": null
}
```

### Tier 3 — Full report
```python
report.to_dict()
report.to_dict(include_full_diff=True)
```

## Top-Level Report Schema (FROZEN)

```json
{
  "pipeline_schema_version": "3.4.0",
  "result_status": "success",
  "completed_at": "<iso-8601 utc>",
  "project_path": "<str>",
  "current": {
    "graph_id": "<uuid>",
    "build_id": "<uuid>",
    "content_hash": "<64-char hex>",
    "stats": {
      "nodes": <int>,
      "edges": <int>,
      "files": <int>,
      "classes": <int>,
      "methods": <int>,
      "functions": <int>,
      "external": <int>
    }
  },
  "cache": {
    "enabled": <bool>,
    "status": "<enum>",
    "cache_dir": "<str or null>",
    "content_path": "<str or null>"
  },
  "comparison": {
    "status": "<enum>",
    "prior_content_hash": "<hex or null>",
    "prior_build_id": "<uuid or null>",
    "diff_summary": {<diff counts> or null},
    "diff_warnings": [<strings> or null]
  },
  "derived": {
    "has_changes": <bool>,
    "change_counts": {<six int counters>},
    "compared_against_explicit_hash": <bool>
  },
  "warnings": [<strings>]
}
```

## Enum Values (FROZEN)

### `result_status`
- `"success"` — build, serialize, and (optionally) cache completed

Future Stage 3.6+ may add additional values. Consumers should treat
unknown values as non-success but should NOT depend on exhaustiveness.

### `cache.status`
- `"saved"` — new content file persisted
- `"deduplicated"` — content already cached; only refs updated
- `"disabled"` — no cache_dir configured
- `"save_skipped"` — caller passed skip_cache_save=True

### `comparison.status`
- `"no_prior"` — cache enabled but no prior entry for this graph_id
- `"prior_corrupt"` — cache returned invalid prior entry (soft-handled)
- `"compared"` — diff computed successfully
- `"comparison_disabled"` — no cache configured

## Determinism Guarantees

| Invariant | Holds for |
|---|---|
| Same project + same cache state → same content_hash | All runs with PYTHONHASHSEED=0 |
| Two consecutive identical-content runs → diff.identical=True | Cached mode |
| Same content → same stats | All modes |
| build_id differs between runs | Always |
| completed_at differs between runs | Always (timestamp) |

## What This API Does NOT Provide

- File-watching (not in scope for Stage 3.x)
- Partial rebuild (Stage 5+)
- Multi-project orchestration
- Background workers
- Streaming progress callbacks
- CLI/MCP wire format (consumers wrap this output for their transport)

## Stability Promise

Stage 3.5.0 commits that:
1. No key currently in `to_dict()` will be renamed or removed without a
   major schema bump.
2. New keys MAY be added in any 3.x release (additive only).
3. Enum values listed above will not change semantics. New enum values
   MAY be added in 3.x.
4. `to_summary_dict()` shape is the most stable of the three tiers.

## Schema Version History

- `3.4.0` — Initial freeze point. Top-level keys: pipeline_schema_version,
  completed_at, project_path, current, cache, comparison, warnings.
- `3.4.0` (Stage 3.5.0 additive): added `result_status`, `derived` block.
  Same major version because no existing key changed.