# Proposed Issue — Composer emits unparseable `for_each(do=lambda)` + swallows blueprint YAML on failure

## Title

`fix(composer): for_each lambda shape from real task still trips extraction; surface blueprint YAML on ComposerError`

## Labels

`bug`, `composer`, `p1`, `research-blocker`

## Summary

Two bugs, discovered together, bundled because they compound each other:

1. **Composer output defeats the `for_each` lambda extractor** even after #57 and #58. A realistic research task (log aggregation: filter → group → count → sort → top-K) produces a blueprint whose `for_each(do=lambda ...)` shape raises:
   > `ValueError: for_each: could not extract brick name from do= callable. Ensure the lambda calls exactly one step.brick_name(...).`
2. **On compose failure the blueprint YAML is discarded** (empty string in `result["blueprint_yaml"]`). The composer raises before emitting the artifact we most need to diagnose what it generated.

The first is a correctness bug. The second is a research-ergonomics bug that makes the first untriageable — every failed run is a $1.25 / ~8-minute black box.

## Reproduction

From `bench-runs` worktree at sha `1c203b83d4b7da1335584bea6e8b3188b2c9c1a8` (main, includes #57 + #58):

```bash
python cases/log-analysis/generate.py 200
python tracks/track-1-exploration/run.py --case log-analysis --size 200 --model sonnet
```

Writes `runs/track-1-exploration_<uuid>.json`. The `bricks.error` field contains the stack.

Deterministic: three runs across two shas (d80c190 pre-fix, 1c203b8 post-fix), identical error message.

Task prompt the composer receives (from [`tracks/track-1-exploration/run.py`](../tracks/track-1-exploration/run.py) `CASES["log-analysis"]["bricks_task"]`):

> Given a list of log line strings under inputs.log_lines, compute (a) severity_counts: a dict mapping each severity in [INFO, WARN, ERROR, DEBUG] to the count of parseable lines at that severity (unparseable lines are ignored), and (b) top_error_patterns: the top 3 distinct message strings among ERROR lines, as a list of {pattern, count} dicts sorted by count descending then pattern ascending. Log line format is '<ISO-timestamp> <SEVERITY> <service> - <message>' with some noise.

## Observed cost of the failure

| Run | Sha | Cost USD | Wall s | Output tokens | Result |
|---|---|---|---|---|---|
| 1 | d80c190 | — | 120 | — | provider timeout (old 120s default) |
| 2 | d80c190 | 1.247 | 596 | 48,685 | `for_each` extraction ValueError |
| 3 | 1c203b8 | 1.230 | 493 | 33,202 | **same** `for_each` extraction ValueError |

Full run records: `runs/track-1-exploration_{2c36fb8c,00ab797c}*.json` in this worktree. Notable: `runs/notable/d80c190-log-analysis-compose-failure.md`.

## Root cause hypothesis

#58 added a passing integration test for `for_each(do=lambda ... brick(...))`, so the shape under test works. Our composer-generated lambda is **different** — likely either (a) multi-statement/multi-call, (b) uses a nested call, or (c) binds variables outside the single-brick pattern the extractor expects. Without the blueprint YAML (bug #2) we can't pin down which.

## Proposed fix

### (1) Surface blueprint YAML on composer errors

`ComposerError` should carry the generated YAML (even if it failed to parse or validate). Two options:

- Add `blueprint_yaml: str` attribute on `ComposerError` and populate wherever the composer raises post-generation.
- Or: always write the raw LLM output to `result["blueprint_yaml"]` in the orchestrator's failure path, not just the success path.

Either unblocks RA's ability to file future composer bugs with reproducers.

### (2) Either expand `for_each` extractor or constrain composer output

Order of preference:

- **Preferred:** once (1) lands, capture the actual lambda shape this task produces and either extend the extractor to handle it or add a composer-side rule that rejects/rewrites unsupported shapes before emitting.
- **Fallback:** have the composer surface a structured error pointing at the offending step (line number in the YAML) instead of a generic `ValueError` from DAG building.

## Acceptance

- [ ] `ComposerError` exposes the blueprint YAML that triggered the failure; `result["blueprint_yaml"]` is non-empty on failure paths too
- [ ] Re-running the reproducer above either (a) succeeds end-to-end, or (b) fails with a message that identifies the exact step/line in the YAML, and the YAML is visible in the run record
- [ ] A regression test checks the specific lambda shape captured from this failure

## Non-blockers (explicit scope cut)

- Don't redesign `for_each` — just handle the shape the composer actually produces
- Don't touch raw-LLM baseline — it's working
- Raw-sonnet deterministically miscounts `INFO` by 4 (153 vs 157) on this dataset. Separate finding, not a fix target — likely article material.

## Research impact

Track 1 (Exploration) is blocked on this for any non-trivial case. `crm-pipeline` (simpler baseline) may still work and we can try it next, but the story of the article is cost + reliability **across scenario complexity**, and we need compose to survive at least moderate-complexity tasks to tell it.
