# Playground: `cross_dataset_join` expected_output is wrong — both engines correctly compute 18, spec asserts 24

**Reporter:** RA (bench-runs worktree)
**Surface:** Web playground UI, scenario "Orders Customer Join"
**Sha:** `bf68452`
**Severity:** P0 (silently misleads every demo viewer; reads as "Bricks fails on join")
**Labels:** `bug`, `playground`, `scenarios`, `p0`

---

## Summary

The bundled scenario `cross_dataset_join` ([`src/bricks/playground/web/presets/cross_dataset_join.yaml:13`](src/bricks/playground/web/presets/cross_dataset_join.yaml#L13)) declares `expected_outputs: {total_completed: 24}`. The dataset it references ([`src/bricks/playground/web/datasets/orders_customers.json`](src/bricks/playground/web/datasets/orders_customers.json)) actually contains **18** completed orders. Both BricksEngine and RawLLMEngine independently compute `total_completed: 18`, both fail correctness, and the UI ends up saying "Side-by-side results" with both engines marked failing — even though both got the **right** answer relative to the data.

This is the most-visible scenario in the playground (Orders Customer Join is the only multi-table join demo). Reads as "Bricks can't even do a join" when in fact the Bricks blueprint here is one of the strongest in the suite — it correctly emits `step.join_lists_on_key`, even renames `id`→`customer_id` at compose time so the join key matches.

## Reproduction

From the bench-runs worktree at sha `bf68452`:

```bash
.venv/Scripts/pip install -e ".[playground]"
.venv/Scripts/python -m bricks.playground.web   # serves on :8742

# in another shell:
.venv/Scripts/python runs/playground-replay/replay.py
.venv/Scripts/python -c "
import json
d = json.load(open('runs/playground-replay/cross-dataset-join.json'))
print('expected:', d['scenario']['expected_output'])
print('bricks  :', d['result']['bricks']['outputs'])
print('raw_llm :', d['result']['raw_llm']['outputs'])
"
```

Output:

```
expected: {'total_completed': 24}
bricks  : {'basic_revenue': 3758.7, 'pro_revenue': 0.0, 'enterprise_revenue': 687.8, 'total_completed': 18}
raw_llm : {'basic_revenue': 3758.7, 'pro_revenue': 0.0, 'enterprise_revenue': 687.8, 'total_completed': 18}
```

Both engines, exactly the same answer. Verifying directly against the dataset:

```bash
.venv/Scripts/python -c "
import json
data = json.load(open('src/bricks/playground/web/datasets/orders_customers.json'))['data']
print('total orders:', len(data['orders']))
print('completed:',  sum(1 for o in data['orders'] if o.get('status') == 'completed'))
"
# total orders: 50
# completed: 18
```

There are 18 completed orders in the dataset, not 24.

## Fix (one of the following)

**Option A — fix the YAML (recommended, one-line):**

```diff
 expected_outputs:
-  total_completed: 24
+  total_completed: 18
```

While there, consider also adding the per-tier revenue values that both engines compute (basic_revenue: 3758.7, pro_revenue: 0.0, enterprise_revenue: 687.8) so the demo actually checks all four output keys instead of one.

**Option B — regenerate the dataset to match the assertion** if 24 was the intended demo number. The dataset generator (if any — could not find it; data appears hand-rolled) would need to produce 24 completed orders out of 50.

Option A is the correct fix unless there's a written history of why 24 specifically was chosen.

## Why this matters

The playground is the user-facing demo. The verdict logic ([`src/bricks/playground/web/static/index.html:1444-1451`](src/bricks/playground/web/static/index.html#L1444)) renders:

- 0 passes vs 0 passes → "Side-by-side results"
- Both engines marked as failed checks

A casual reader sees a join-shaped task with both engines failing and concludes Bricks can't handle joins. Two real users (an internal viewer and a researcher running this investigation) both made that read before tracing the data. The fix is one digit; the perception cost is high.

## Suggested regression prevention

Add a CI check that every `web/presets/*.yaml` scenario's `expected_outputs` is satisfied by running the **raw_llm** engine against its bundled `data` and asserting at least one engine passes. Or, more cheaply, add a dataset-validity assertion test in [`tests/playground/test_scenario_loader.py`](src/bricks/playground/tests/test_scenario_loader.py) that for each preset, load the data and verify the expected outputs are computable from it (e.g., for `cross_dataset_join`, count the `completed` orders inline and assert it matches `expected_outputs.total_completed`).

## Acceptance

- [ ] `cross_dataset_join.yaml` `expected_outputs.total_completed` matches the actual count in the bundled dataset.
- [ ] Re-running the reproducer above shows at least one engine with non-zero passes.
- [ ] (Stretch) A test ensures dataset/expected consistency for all bundled presets.

## Non-goals

- Do not change Bricks engine behavior. The blueprint it produces here (saved at `runs/playground-replay/cross-dataset-join.json` → `bricks.dsl_code`) is correct and good demo material.
- Do not change the scoring/correctness logic.
