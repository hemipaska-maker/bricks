# Notable — three minimal-task probes surface two distinct Bricks bugs

**Date:** 2026-04-22
**Sha:** `20dc0cc` (includes #57, #58, #63/#64 for_each fixes)
**Model:** sonnet
**Cost of this probe batch:** Bricks $0.28, raw LLM $0.09

## Setup

Three sibling single-reducer tasks on the same N=50 numeric dataset (`cases/numeric-stats/data-50.json`):

- `sum-only` — "return {sum: S}"
- `count-only` — "return {count: N}"
- `max-only` — "return {max: M}"

Goal: isolate which engine phase (compose / DSL extraction / execution) is failing. Small tasks with clean expected DSL output.

## Results

| Case | Bricks | Composer output | Execution error |
|---|---|---|---|
| sum-only | ❌ | `step.reduce_sum(values=values)` | `reduce_sum` failed: `'NoneType' object is not iterable` |
| count-only | ❌ | `step.count_dict_list(items=values)` | `count_dict_list` failed: `object of type 'NoneType' has no len()` |
| max-only | ❌ | `for_each(...) → map_values → calculate_aggregates(...)` | `Brick not found: '__for_each__'` |

Raw-LLM baseline got all three correct.

## Bug A — Flow-parameter input binding returns None

**Triggered by:** sum-only, count-only. Both have clean, minimal composer output using a single brick. No `for_each`, no complex shape.

The composer emits:

```python
@flow
def sum_values(values):
    total = step.reduce_sum(values=values)
    return {"sum": total}
```

Invoked via `Bricks.default().execute(task, inputs={"values": [...]})`. The `values` parameter of the `@flow`-decorated function is supposed to bind to `inputs.values`, then flow into the brick call as `reduce_sum(values=values)`. At execute time, the brick sees `values=None`.

Either:
- The `@flow` decorator doesn't register its named parameters as input slots (input list is empty → nothing maps), **or**
- The input mapper in `RuntimeOrchestrator` doesn't match the flow signature against the `inputs` dict.

Composer output for both cases saved:
- `runs/notable/composer-raw-20260422-191721.py` (sum-only, 98 chars)
- `runs/notable/composer-raw-20260422-191750.py` (count-only, 106 chars)

## Bug B — `for_each` step serialises to brick lookup `__for_each__`

**Triggered by:** max-only, numeric-stats (earlier run). Any task where the composer reaches for `for_each` to wrap a raw list before aggregating.

Composer output is valid DSL:

```python
wrapped = for_each(items=values, do=lambda item: step.set_dict_field(data={}, field="v", value=item))
max_val = step.calculate_aggregates(items=wrapped.output, field="v", operation="max")
```

DSL layer accepts it (no more `could not extract brick name` — #58/#63 fixed that). But at engine execute time, some step has `brick_name="__for_each__"` and the registry raises `BrickNotFoundError`.

The `__for_each__` placeholder comes from `dsl.py`:

```python
do_brick: str = first.brick_name or f"__{first.type}__"
```

Normally `first.brick_name` is set (e.g. `"set_dict_field"`). For this to produce `__for_each__`, either:
- The inner tracer in `for_each` is recording a `for_each`-typed Node as `first` instead of the brick the lambda calls, **or**
- A separate code path uses `__{type}__` for the outer for_each step and the engine's step dispatch reads it as a brick name.

Hypothesis 2 looks more likely — engine.py:218 does `self._registry.get(brick_name)` without first checking step type.

## Underlying pattern

The composer emits different shapes based on whether a direct reducer brick exists:

- **Direct reducer available** (`reduce_sum`, `count_dict_list`): clean, no `for_each`. Hits Bug A.
- **No direct reducer** (no `reduce_max` seemingly): composer wraps the list into dicts via `for_each` + `set_dict_field` so `calculate_aggregates(field=...)` can operate on it. Hits Bug B.

Either bug alone is enough to keep Bricks at a 0% success rate on any list-input task on this sha.

## Cost / token snapshot (N=50 each)

| Engine | Case | Input tokens | Output tokens | Cache read | Cost USD | Duration |
|---|---|---|---|---|---|---|
| Bricks | sum-only | 3 | 1083 | — | 0.064 | 10.7s |
| Bricks | count-only | 3 | 698 | — | 0.043 | 7.0s |
| Bricks | max-only | — | 2815 | — | 0.170 | 71.8s |
| RawLLM | sum-only | 3 | 1408 | 25k | 0.048 | 15.7s |
| RawLLM | count-only | 3 | 552 | 25k | 0.020 | 6.0s |
| RawLLM | max-only | 3 | 552 | 25k | 0.020 | 5.3s |

Sonnet's direct answer on these tiny reductions is about $0.02–0.05; Bricks' compose alone is $0.04–0.17 and then fails.

## Next probes (if continuing)

1. **Confirm Bug A's scope**: try a task with an explicit input reference — e.g., give the task prompt wording that pushes the composer to use `inputs.values` pattern instead of a flow parameter. If that works, it's purely a signature-binding issue. If it also fails, the whole input-plumbing layer is broken.
2. **Try a non-list input**: single-dict task (e.g., "given inputs.record = {a: 1, b: 2}, return {sum: a+b}"). If this works and lists don't, the bug narrows to list handling.
3. **`branch` probe**: does a task with a simple conditional (no for_each) execute? Isolates Bug B.

Total probe budget so far: ~$0.37. Three more probes ~ another $0.30. Full cost-curve sweep is still gated on at least one of these bugs being fixed.
