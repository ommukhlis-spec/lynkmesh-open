# Artifacts — mini_auth_shop_php_001

> **Status: captured.** These deterministic LynkMesh artifacts have been
> generated on a host with PHP available and committed to this directory. The
> commands below document exactly how to regenerate them. Do not hand-edit
> generated artifacts; do not fabricate them.

## Generation commands

Run from the repo root (`...\lynkmesh`) with the package importable
(installed, or `set PYTHONPATH=..` from inside the repo), `PYTHONHASHSEED=0` for
deterministic output:

```bash
FIX=evals/before_after/fixtures/mini_auth_shop_php
OUT=evals/before_after/runs/mini_auth_shop_php_001/artifacts

python -m lynkmesh doctor > "$OUT/doctor_output.txt" 2>&1
python -m lynkmesh report "$FIX" --pretty > "$OUT/report_output.json"
python -m lynkmesh pack "$FIX" --profile compact --pretty > "$OUT/pack_output.json"
python -m lynkmesh pack "$FIX" --profile expanded --pretty > "$OUT/pack_expanded_output.json"
python -m lynkmesh benchmark "$FIX" --profile compact --pretty > "$OUT/benchmark_output.json"
python -m lynkmesh benchmark "$FIX" --profiles compact,balanced,expanded --pretty > "$OUT/benchmark_all_profiles_output.json"
```

Windows (cmd):

```bat
set PYTHONHASHSEED=0
set FIX=evals\before_after\fixtures\mini_auth_shop_php
set OUT=evals\before_after\runs\mini_auth_shop_php_001\artifacts

python -m lynkmesh doctor > "%OUT%\doctor_output.txt" 2>&1
python -m lynkmesh report "%FIX%" --pretty > "%OUT%\report_output.json"
python -m lynkmesh pack "%FIX%" --profile compact --pretty > "%OUT%\pack_output.json"
python -m lynkmesh pack "%FIX%" --profile expanded --pretty > "%OUT%\pack_expanded_output.json"
python -m lynkmesh benchmark "%FIX%" --profile compact --pretty > "%OUT%\benchmark_output.json"
python -m lynkmesh benchmark "%FIX%" --profiles compact,balanced,expanded --pretty > "%OUT%\benchmark_all_profiles_output.json"
```

## Expected files after generation

- `doctor_output.txt` — environment diagnostics (research preview banner).
- `report_output.json` — deterministic MeshContext Report for the fixture.
- `pack_output.json` — AI Context Pack (compact) for the fixture.
- `pack_expanded_output.json` — AI Context Pack (expanded) for the fixture;
  this is the readable evidence-index artifact consumed by the AFTER capture.
- `benchmark_output.json` — Token Benchmark (compact) for the fixture.
- `benchmark_all_profiles_output.json` — Token Benchmark across the compact,
  balanced, and expanded profiles.

## Validate after generation

```bash
python -m json.tool report_output.json > /dev/null
python -m json.tool pack_output.json > /dev/null
python -m json.tool pack_expanded_output.json > /dev/null
python -m json.tool benchmark_output.json > /dev/null
python -m json.tool benchmark_all_profiles_output.json > /dev/null
```

Confirm each artifact declares no LLM inference (`contains_llm_inference: false`
in report provenance / pack guardrails / benchmark guardrails) and contains no
unexpected private paths before committing.
