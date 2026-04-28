# Bricks: 0/4 success rate on list-input tasks at `20dc0cc` — two independent bugs

**Reporter:** RA (bench-runs worktree)
**Evidence:** 4 independent Track-1 runs, sha `20dc0cc` (post #57, #58, #63/#64), model `sonnet`
**Total cost to reproduce this report:** $1.56 (Bricks side) + $0.48 (raw LLM baseline) = $2.04
**Labels to apply:** `bug`, `composer`, `orchestrator`, `p0`, `research-blocker`

---

## TL;DR

Every Track-1 research task that takes a list as input fails — **0 out of 4** cases at this sha. Two independent bugs both have to be hit to succeed; neither alone is the full story:

- **Bug A — `@flow` parameter binding returns `None`.** The simplest possible pipeline (`step.reduce_sum(values=values)`) fails because the `values` function parameter is not wired to `inputs.values`. Affects clean composer output.
- **Bug B — `for_each` steps resolve to a brick name `__for_each__`.** Blueprint execution raises `BrickNotFoundError: '__for_each__'` on any task the composer wraps with `for_each`. Persists after #57, #58, #63, #64.

Either bug alone keeps Bricks at 0% on list-input tasks. Both need fixing to unblock Track 1 (cost-curve exploration).

## Reproduction environment

- Worktree: `Bricks/Code/bench-runs` on detached HEAD
- Sha: `20dc0ccef8b1d1c6ca73c3bf9f8caaed7c82fcbd` (origin/main HEAD as of 2026-04-22; merge of #63/#64 — "for_each static_kwargs + DSL_PROMPT_TEMPLATE example B correctness")
- Python: 3.10 (Windows 11, `.venv/Scripts/python.exe`)
- Bricks install: `pip install -e ".[dev]"` from worktree root
- Provider: `ClaudeCodeProvider(model="sonnet", timeout=600)` (local `claude` CLI with `--output-format json`)
- Task runner: `tracks/track-1-exploration/run.py` (this worktree; writes a JSON record per run under `runs/` + appends a line to `manifest/track-1.jsonl`)
- Debug shim: `debug_capture.py` at worktree root — monkey-patches `BlueprintComposer._parse_dsl_response` to dump raw LLM-generated DSL to `runs/notable/composer-raw-<ts>.py` before parsing

---

## Bug A — `@flow` parameter binding: brick receives `values=None`

### Severity

**P0 for research runs.** Blocks the minimal Bricks pipeline — one brick, one input. If this doesn't work, nothing does.

### Reproducer

From bench-runs worktree at sha `20dc0cc`:

```bash
# Generate data (tiny, 50 floats) if not already present
python cases/numeric-stats/generate.py 50

# Run the sum-only task (composer picks reduce_sum, no for_each involved)
python debug_capture.py --case sum-only --size 50 --model sonnet
```

### Composer output (verbatim, saved to `runs/notable/composer-raw-20260422-191721.py`)

```python
@flow
def sum_values(values):
    total = step.reduce_sum(values=values)
    return {"sum": total}
```

This is *clean*. Minimal shape. No `for_each`, no wrappers. Exactly what the DSL was designed for.

### Observed

```
OrchestratorError: Blueprint execution failed for task '...':
  Brick 'reduce_sum' failed at step 'step_1_reduce_sum':
    'NoneType' object is not iterable
```

Run record: `runs/track-1-exploration_15b3062b-c3cf-4ad2-8038-f29de94ff98c.json`. Bricks cost: $0.064, 10.7s, 1 LLM call (compose only), 1083 output tokens.

### Expected

`sum_values` should be invoked with `values = [ <50 floats> ]` taken from the `inputs={"values": [...]}` dict passed to `engine.execute(task, inputs={"values": [...]})`, and `reduce_sum` should then receive that same list.

### Why we think the function parameter isn't wired

Same failure pattern on a sibling task:

```bash
python debug_capture.py --case count-only --size 50 --model sonnet
```

Composer output (`runs/notable/composer-raw-20260422-191750.py`):

```python
@flow
def count_values(values):
    count = step.count_dict_list(items=values)
    return {"count": count}
```

Same error shape: `count_dict_list` failed: `object of type 'NoneType' has no len()`. `values` is again `None` at execute time.

Run record: `runs/track-1-exploration_2ee20181-e21f-4004-8a17-46fb8b2a4310.json`.

Two distinct bricks, two distinct composer-generated flows, same "argument is None" symptom. Points at an upstream input-plumbing layer, not a per-brick issue.

### Hypotheses (one of these)

1. The `@flow` decorator doesn't register the wrapped function's named parameters as Blueprint input slots → the orchestrator sees an empty input list and therefore ignores our `inputs={"values": [...]}`.
2. `RuntimeOrchestrator`'s input mapper doesn't match the flow signature against the `inputs` dict — e.g. it expects an `inputs.values` reference in the DSL code rather than a plain function parameter.
3. The composer's system prompt encourages `def f(values): ... step.X(values=values)` style even though the orchestrator expects explicit `inputs.values` references. (If true, this is a prompt-vs-runtime contract mismatch; the fix is in the composer prompt, not the orchestrator.)

The `DSL_PROMPT_TEMPLATE` (referenced in commit `20dc0cc` title) would be the place to audit first.

### Acceptance for Bug A

- [ ] `engine.execute(task="return {sum: S} where S is sum of inputs.values", inputs={"values": [1.0, 2.0, 3.0]})` returns `{"sum": 6.0}` without error.
- [ ] No regression in existing tests that use structured `Bricks.from_config(...)` flows.

---

## Bug B — `for_each` steps serialise to brick name `__for_each__`

### Severity

**P0 for research runs.** Blocks every composer path that wraps a list (which is most of them — the composer falls back to `for_each` whenever no single-brick reducer exists).

### History

- #57: "attribute for_each / branch inner failures to the real brick" — didn't cover this path.
- #58: "for_each honours lambda kwarg binding + integration test coverage" — added test for a shape that passes; ours is different and still fails.
- #63/#64: "for_each static_kwargs + DSL_PROMPT_TEMPLATE example B correctness" — still fails on real composer output.

### Reproducer

```bash
python debug_capture.py --case max-only --size 50 --model sonnet
```

(Same numeric-stats dataset, size 50.)

### Composer output (`runs/notable/composer-raw-20260422-191805.py`)

```python
@flow
def find_max(values):
    wrapped = for_each(items=values, do=lambda item: step.set_dict_field(data={}, field="v", value=item))
    dicts   = step.map_values(items=wrapped.output, key="result")
    max_val = step.calculate_aggregates(items=dicts.output, field="v", operation="max")
    return {"max": max_val}
```

The composer wraps each number into a `{"v": n}` dict via `for_each` + `set_dict_field`, then runs `calculate_aggregates` with `field="v"`. This is exactly the idiom taught by the composer system prompt for the "no direct reducer" case (see `src/bricks/ai/composer.py:103` and surrounding DSL examples).

### Observed

```
OrchestratorError: Blueprint execution failed for task '...':
  Brick not found: '__for_each__'

... traceback culminating in:
BrickNotFoundError: Brick not found: '__for_each__'
  at bricks.core.registry.py:50
  called from engine.py:218 → callable_, meta = self._registry.get(brick_name)
```

Run record: `runs/track-1-exploration_6499e7f2-4fa2-4d7f-80e8-5db091231255.json`. Bricks cost: $0.170, 71.8s, 2815 output tokens, 1 LLM call.

### Where `__for_each__` comes from

`src/bricks/core/dsl.py:280–281`:

```python
first = inner_nodes[0]
do_brick: str = first.brick_name or f"__{first.type}__"
```

Normally `first.brick_name` is set (here it'd be `"set_dict_field"`). For the `__for_each__` placeholder to bubble all the way to the registry lookup, **the outer `for_each` node itself is being dispatched through the brick-step code path** (`engine.py:218`) rather than through a `for_each`-aware step handler.

Either:
- The blueprint's step-type dispatcher in `engine._execute_step` (around line 196) falls through to `_execute_brick_step` when it should be routing `type="for_each"` nodes to a for-each executor, **or**
- Blueprint serialisation is collapsing the `for_each` node's `type` field into its `do`/`brick_name` slot, losing the type metadata by the time it reaches the engine.

### Earlier failure modes on this same bug path

Previous `for_each` failure on `log-analysis` (size=200, two separate runs, $2.48 total) was `ValueError: for_each: could not extract brick name from do= callable.` at `dsl.py:276`. That was fixed by #58/#63 — composer now emits valid lambda shapes. **The execution-time bug shown here is a different, downstream failure on the same code path.**

### Acceptance for Bug B

- [ ] `find_max` blueprint above executes successfully against `inputs={"values": [3.0, 1.0, 2.0]}` and returns `{"max": 3.0}`.
- [ ] A regression test captures exactly the composer-emitted shape above (`for_each` → `set_dict_field` → `calculate_aggregates`, not the synthetic shape from #58's test).
- [ ] `engine._execute_step` routes `type="for_each"` steps to a for-each handler and never calls `_execute_brick_step` for them.

---

## Evidence bundle

All artefacts live in the bench-runs worktree. Attach these to the Issue:

**Run records (full JSON, one per task):**

- `runs/track-1-exploration_15b3062b-c3cf-4ad2-8038-f29de94ff98c.json` — sum-only, Bug A
- `runs/track-1-exploration_2ee20181-e21f-4004-8a17-46fb8b2a4310.json` — count-only, Bug A
- `runs/track-1-exploration_6499e7f2-4fa2-4d7f-80e8-5db091231255.json` — max-only, Bug B
- `runs/track-1-exploration_a782ccb3-be3b-4796-9fdf-dc83abf5394b.json` — numeric-stats N=50, Bug B (earlier)

**Composer-generated DSL source (verbatim LLM output):**

- `runs/notable/composer-raw-20260422-191721.py` — sum_values
- `runs/notable/composer-raw-20260422-191750.py` — count_values
- `runs/notable/composer-raw-20260422-191805.py` — find_max
- `runs/notable/composer-raw-20260422-180958.py` — summarize_numbers (numeric-stats, identical pattern to find_max)

**Analysis notes (prior context):**

- `runs/notable/d80c190-log-analysis-compose-failure.md` — history of #57/#58 not covering our case
- `runs/notable/20dc0cc-three-probes-two-bugs.md` — this batch, cost table, hypotheses

**Earlier proposals (supersede with this Issue):**

- `proposals/issue-compose-for_each-and-yaml-visibility.md` — from before Bug A was isolated

---

## Research-ergonomics asks (nice-to-have, same PR or split)

1. **Surface blueprint YAML on `ComposerError` / `OrchestratorError`.** `result["blueprint_yaml"]` is `""` on any failure path, so Coder can't see what the composer actually emitted. The debug shim we wrote is a monkey-patch workaround; the engine should do this natively.
2. **Include brick dispatch type in `BrickNotFoundError`.** Saying "brick `__for_each__` not found" is misleading — `__for_each__` is a flow-type placeholder, not a real brick name anyone would register. Error should say something like "Step type `for_each` routed to brick dispatcher — this is an engine bug" so the next reporter doesn't chase "missing brick" red herrings.

---

## Non-goals (don't scope-creep this Issue)

- No budget/timeout feature work (separate issue)
- No composer prompt overhaul beyond the `DSL_PROMPT_TEMPLATE` audit needed for Bug A
- No raw-LLM baseline changes — raw side is working (deterministic miscounting by 4 on log-analysis N=200 is a separate article finding, not a fix)
- No cost-curve / cache-tier work — that's Track 1's deliverable, gated on this fix landing

---

## Research impact if unfixed

Track 1 ("Cost curve: at what data size does Bricks start winning on cost?") cannot produce any Bricks data points on list-input tasks until at least one of A or B is fixed. Raw-LLM-only findings can still ship, but the central comparison the article is built on is on hold. Suggest P0 given how small the fix surface likely is for Bug A (prompt/decorator) and how localised Bug B is (engine step dispatch).
