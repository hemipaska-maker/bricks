# Notable — Bricks compose failure on log-analysis @ d80c190

**Date:** 2026-04-21
**Run:** `runs/track-1-exploration_2c36fb8c-41ed-4f22-8afd-5affca3995cc.json`
**Sha:** `d80c190` (post-#49 merge)
**Case:** `log-analysis`, size=200, model=sonnet

## What happened

First real Track 1 run post-#49. Bricks failed at compose with:

```
ValueError: for_each: could not extract brick name from do= callable.
Ensure the lambda calls exactly one step.brick_name(...).
```

No blueprint YAML was returned (empty string), suggesting the error fires inside the composer before the blueprint is stored.

## Cost of the failure

- 1 LLM call, 596 seconds wall, 48,685 output tokens, $1.247
- This is a single compose attempt — no heal retry cascade visible. The composer produced a blueprint with an unparseable `for_each(do=lambda ...)` form and raised before emitting YAML.

## Possible readings

1. **Composer bug** — the composer is generating DSL shapes the validator rejects. The error message itself ("ensure the lambda calls exactly one step.brick_name(...)") reads like a runtime assertion in the DSL layer that the composer's output happens to violate. Suggests a template-vs-validator drift.
2. **Prompt underspecification** — our task prompt (`bricks_task` in [run.py](../../tracks/track-1-exploration/run.py)) describes the intent in natural language; the composer had to infer a filter→group→count→sort chain and chose a `for_each` pattern the DSL can't verify.
3. **Catalog gap** — if there's no native group-by-and-count brick, the composer may be trying to emulate one with a `for_each` + accumulator, and falling off the happy path.

No way to discriminate (1) from (2)/(3) without the blueprint YAML. The composer swallowing the YAML on validation failure is itself a research-ergonomics issue — we lose the artifact we most need to diagnose.

## Raw-LLM comparison (same run)

Raw sonnet got `top_error_patterns` exactly right but miscounted INFO by 4 (153 vs 157). Same miscount in the earlier timed-out run — deterministic on this seed. Classic LLM counting failure even at 200 items. $0.29/run.

## Update 2026-04-22 — recurs at 1c203b8 (post #57 + #58)

Retried at `1c203b8` which includes both #57 ("attribute for_each / branch inner failures to the real brick") and #58 ("for_each honours lambda kwarg binding + integration test coverage"). **Identical error, identical signature**:

> `ValueError: for_each: could not extract brick name from do= callable. Ensure the lambda calls exactly one step.brick_name(...).`

Run: `runs/track-1-exploration_00ab797c-fbb4-431e-b2ed-b3e798b2b90a.json`. Cost $1.23, 493s, 33k output tokens, blueprint YAML still empty. Raw LLM still deterministically miscounts INFO by 4 (153 vs 157) — confirmed across three runs on the same seed.

So #57/#58 did not cover the path the composer is taking on this task. Either:
- The composer is emitting a lambda shape outside the cases those PRs exercised (likely — the new integration test in #58 passes, so the shape under test works; ours is different).
- The extraction logic that raises this message still has an uncovered case.

**Two-run total spend on this failure: $2.48.** Raw-LLM comparison runs cost $0.29–0.38 each.

## Suggested next steps

- [ ] Flag to Coder: surface blueprint YAML in `ComposerError` / at least log it before raising, so failed compose is still diagnosable. Draft proposal if confirmed.
- [ ] Flag to Coder: investigate whether this `for_each(do=lambda...)` shape is a known composer output or a regression.
- [ ] On RA side: don't retry until above is understood — a second $1.25 burn won't teach us anything new.
- [ ] Consider a smaller-size smoke run (size=50) on a different, simpler case (`crm-pipeline` baseline) to confirm the compose path works somewhere before blaming it.
