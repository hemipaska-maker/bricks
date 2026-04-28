# Notable — Bug C: `for_each` lambda extractor crashes on `item["key"]` subscripting

**Date:** 2026-04-27
**Sha:** `bf68452` (post-#66 — A and B already fixed)
**Case:** `log-analysis` N=200, model=sonnet
**Run:** `runs/track-1-exploration_2a364771-7e4d-4638-97e0-0cc8a6d7a2d1.json`
**Composer DSL:** `runs/notable/composer-raw-20260427-230202.py`
**Lambda diagnostic:** `runs/notable/for_each-lambda-20260427-230202.txt`

## Summary

Even after #57/#58/#63/#66 fixes, log-analysis at N=200 still fails — but with a new and different root cause. The composer now produces a **valid, idiomatic** blueprint (14 bricks chained), and #60's widened error message lets us pinpoint the exact line:

> `Inner lambda raised: TypeError: 'Node' object is not subscriptable`

## The offending pattern

The composer-emitted DSL contains:

```python
filtered_per = for_each(
    items=unique_pats.output,
    do=lambda pat: step.filter_dict_list(items=msg_dicts.output, key="pattern", value=pat["pattern"])
)
```

This is a perfectly normal Python pattern: iterate over dicts, pluck a field with `pat["pattern"]`, pass it as an argument. Any real composer output that does filtering or grouping over dict-shaped items will look like this.

## Why it crashes

Bricks' `for_each` extractor in `dsl.py:266-280` runs the lambda once with a mock `Node` injected as `item`:

```python
mock = Node(type="brick", brick_name="__mock__", params={})
try:
    do(mock)
except Exception:
    pass  # tracer should still have recorded the inner step.X(...) call
```

The mock is a `Node`, not a dict. `mock["pattern"]` raises `TypeError: 'Node' object is not subscriptable`. The exception fires *before* `step.filter_dict_list(...)` is reached, so the tracer records zero inner nodes, and the extractor raises:

> `for_each: could not extract brick name from do= callable.`

## Why this is a new bug (not a regression)

#57/#58/#63/#66 fixed cases where the lambda body called `step.X(item)` directly (item passed opaquely). They added passing tests for those shapes. Subscripting the iteration variable is a different shape — common in real blueprints, never tested.

Three previous bugs all fixed:
- A: `@flow def f(values): step.X(values=values)` — fixed by #66 (param binding)
- B: `for_each` step routing as `__for_each__` brick — fixed by #66
- The original "could not extract" — fixed by #63 for opaque-item lambdas

This bug C is what's left: the extraction trick fundamentally can't handle subscriptable item access, because the mock injected isn't subscriptable.

## Suggested fixes

The compiler-style fix: stop relying on tracing-by-execution to extract the lambda's intent. Instead, AST-parse the lambda body at compose time. We already have AST validation; extending it to extract:
- The single `step.X(...)` call
- Which kwargs reference the iteration variable (whether opaquely or via subscript/attr access)
- Static tracking of `item["key"]` as a field-pluck

would be deterministic and would catch malformed lambdas at compose time, not at the runtime tracer.

A cheaper local fix: replace `mock = Node(...)` with a `MagicNode` subclass that's both a Node *and* subscriptable / attributable into more Nodes, so `mock["pattern"]` returns a Node-shaped placeholder that the inner call accepts.

## Other observation: N=50 timed out at compose

N=50 with the same task had Bricks compose **timeout at 600s with $0 spent** (no successful LLM call return). Run record `runs/track-1-exploration_f7f21c08-3577-4a79-ba52-aa11219f9c46.json`. Different failure mode — compose itself didn't return, possibly because the post-#66 expanded brick catalog made the composer's planning phase longer-running. Worth flagging separately if it recurs.

## Raw-LLM baseline on the same data

| N | INFO actual | INFO expected | Other miscounts | top_error_patterns |
|---|---|---|---|---|
| 50 | 35 | 36 | ERROR 3 vs 4 | Wrong (picked one of the tied patterns randomly) |
| 200 | 153 | 157 | (none) | Correct |

Sonnet raw-LLM consistently miscounts by small amounts on this dataset across all log-analysis runs. Off-by-1 at N=50, off-by-4 at N=200 (deterministic across multiple sessions). Article material — "LLMs are bad at counting, even with the data right in front of them."

## Status for Track 1

- Numeric tasks (`sum-only`, `count-only`, `max-only`, `mean-only`, `numeric-stats`): all working post-#66.
- String/parsing tasks (`log-analysis`): blocked on Bug C.

Pivoting to multi-model curve on numeric tasks (where Bricks works) for the article's headline figure. Will queue Bug C as a follow-up Issue (separate from #66).
