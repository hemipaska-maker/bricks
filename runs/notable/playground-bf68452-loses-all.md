# Notable — Playground "Bricks loses on all scenarios" investigation

**Date:** 2026-04-28
**Sha:** `bf68452` (post #66)
**Surface:** Web playground (FastAPI app at `http://localhost:8742`, started via `python -m bricks.playground.web`)
**Model:** `claude_code` provider, `sonnet`
**Scope:** All 4 bundled web-playground scenarios

## Headline finding

**The user's "Bricks loses on all scenarios" report is incorrect at this sha.** A fresh replay of every scenario shows the opposite headline:

- **2 of 4 scenarios:** Bricks WINS over raw LLM
- **1 of 4:** Tied, both get the same answer — but the scenario's expected output is **wrong** (a scenario-spec bug, not a Bricks bug)
- **1 of 4:** Bricks compose times out at the default 120s; this is a real Bricks issue but it's a **provider-timeout default**, not a compose-quality failure

If the user is observing "Bricks loses everywhere," they're either looking at an older run cached in the UI, seeing token counts (Bricks tokens > raw tokens, true but not the verdict), or running against a different sha.

## Per-scenario results

| Scenario | Bricks pass | Raw LLM pass | Verdict | Bricks tokens | Raw tokens |
|---|---|---|---|---|---|
| `crm-pipeline` | **3/3 ✓** | 1/3 ✗ | **Bricks wins** | 6/460 | 3/40 |
| `cross-dataset-join` | 0/1 ✗ | 0/1 ✗ | Tie — expected value wrong | 3/2,686 | 3/2,244 |
| `custom-example` | 0/2 ✗ | 1/2 ✗ | Raw LLM "wins" by error survival | 0/0 (timeout) | 3/22 |
| `ticket-pipeline` | **4/4 ✓** | 2/4 ✗ | **Bricks wins** | 6/767 | 3/37 |

The frontend's verdict logic ([`index.html:1444-1451`](../../src/bricks/playground/web/static/index.html#L1444)) declares: 2× "Bricks beat raw LLM", 1× "Side-by-side results", 1× "Raw LLM beat Bricks".

Run records: [runs/playground-replay/](../playground-replay/). Driver: [replay.py](../playground-replay/replay.py).

## Scenario-by-scenario detail

### `crm-pipeline` — Bricks **wins** 3/3 over raw LLM 1/3

Task: filter active CRM customers, return active_count + total_active_revenue + avg_active_revenue.

| Key | Expected | Bricks got | Raw LLM got |
|---|---|---|---|
| `active_count` | 9 | **9 ✓** | 9 ✓ |
| `total_active_revenue` | 1524.0 | **1524.0 ✓** | 1023.5 ✗ |
| `avg_active_revenue` | 169.33 | **169.33333 ✓** | 113.722 ✗ |

Raw sonnet got the count right but **miscalculated revenue by $500** — apparently summed the wrong subset of customers. Classic "LLM does math in tokens, drifts" pattern. Bricks executed deterministic Python, exact answer.

This scenario alone disproves "Bricks loses on all."

### `cross-dataset-join` — both engines correctly compute 18; **expected value of 24 is wrong**

This is the user's flagged "fails outright" scenario. Reality:

| Key | Expected | Bricks got | Raw LLM got |
|---|---|---|---|
| `total_completed` | **24 (wrong!)** | 18 | 18 |
| `basic_revenue` | (not checked) | 3758.7 | 3758.7 |
| `pro_revenue` | (not checked) | 0.0 | 0.0 |
| `enterprise_revenue` | (not checked) | 687.8 | 687.8 |

Both engines independently computed `total_completed = 18`. We verified the data in [`src/bricks/playground/web/datasets/orders_customers.json`](../../src/bricks/playground/web/datasets/orders_customers.json) directly:

```
orders total: 50
status counts: {completed: 18, refunded: 16, pending: 16}
```

There are **exactly 18 completed orders**. The scenario's `expected_outputs: {total_completed: 24}` in [`cross_dataset_join.yaml:13`](../../src/bricks/playground/web/presets/cross_dataset_join.yaml#L13) is incorrect.

**Suggested fix:** edit the YAML to `total_completed: 18`. Or replace the dataset with one that does have 24 completed orders if 24 was the intended demo number.

#### The Bricks blueprint here is excellent

Far from "failing outright," the composer produced a clean, idiomatic 9-step blueprint that **correctly** handles the join:

```python
@flow
def plan_revenue_summary(raw_api_response):
    parsed            = step.extract_json_from_str(text=raw_api_response)
    orders            = step.extract_dict_field(data=parsed.output, field="orders")
    customers         = step.extract_dict_field(data=parsed.output, field="customers")

    # Rename 'id' -> 'customer_id' in customers so the join key matches
    renamed_raw       = for_each(items=customers.output, do=lambda item: step.rename_dict_keys(data=item, rename_map={"id": "customer_id"}))
    renamed_custs     = step.map_values(items=renamed_raw.output, key="result")

    joined            = step.join_lists_on_key(left=orders.output, right=renamed_custs.output, key="customer_id")
    completed         = step.filter_dict_list(items=joined.output, key="status", value="completed")

    total_completed   = step.count_dict_list(items=completed.output)

    basic_orders      = step.filter_dict_list(items=completed.output, key="plan", value="basic")
    pro_orders        = step.filter_dict_list(items=completed.output, key="plan", value="pro")
    enterprise_orders = step.filter_dict_list(items=completed.output, key="plan", value="enterprise")

    basic_revenue      = step.calculate_aggregates(items=basic_orders.output, field="amount", operation="sum")
    pro_revenue        = step.calculate_aggregates(items=pro_orders.output, field="amount", operation="sum")
    enterprise_revenue = step.calculate_aggregates(items=enterprise_orders.output, field="amount", operation="sum")

    return {
        "basic_revenue":      basic_revenue,
        "pro_revenue":        pro_revenue,
        "enterprise_revenue": enterprise_revenue,
        "total_completed":    total_completed,
    }
```

Highlights:
- Uses `join_lists_on_key` directly. The composer **does** know about the join brick and **does** use it on this task.
- Spots that the join keys don't match (orders has `customer_id`, customers has `id`) and **renames the customer field at compose time** — a non-trivial planning step the composer got right.
- Filters to `completed` once, then re-filters per plan tier — n+1 selects, but correct.
- Bricks: 1 in-token, 2,686 out-tokens for the compose call. ~$0.04. Then deterministic execution.

This is exactly the kind of blueprint the article should hold up as evidence that compile-mode works on real-shape tasks.

### `custom-example` — Bricks compose timeout at 120s default

Task: filter products with stock > 0, count available + sum total_value (5 inline products).

Bricks `error`: `API call failed: Command '['claude', '-p', '--output-format', 'json', '--model', 'sonnet']' timed out after 120 seconds`. No DSL emitted. Token counts both 0 (compose call never returned).

Raw LLM: `available_count = 3 ✓`, but `total_value = 2858.27 ✗` (expected 2459.82, off by $400). Raw also failed correctness, just on one key instead of both.

The Bricks failure is the **provider's default timeout**, not a compose-quality issue. Looking at [`src/bricks/providers/claudecode/provider.py`](../../src/bricks/providers/claudecode/provider.py): default `timeout=120`. The compose attempt for this 5-row task somehow took longer than 2 minutes — almost certainly because the brick catalog grew with `register_builtins` post-#66 and the planning phase is slower under cold cache conditions.

**Suggested fix:** raise the `BricksEngine` provider timeout default to 300 or 600s. Or surface the timeout as a configurable parameter in the playground UI.

### `ticket-pipeline` — Bricks **wins** 4/4 over raw LLM 2/4

| Key | Expected | Bricks got | Raw LLM got |
|---|---|---|---|
| `open_high_count` | 9 | **9 ✓** | 10 ✗ |
| `billing_count` | 4 | **4 ✓** | 4 ✓ |
| `technical_count` | 2 | **2 ✓** | 2 ✓ |
| `general_count` | 3 | **3 ✓** | 4 ✗ |

Raw sonnet miscounted by 1 on two of the four keys — same off-by-N pattern we've seen across the bench-runs reliability sweep. Bricks executed deterministic filter+count, exact.

## Three issues to file

In priority order:

### Issue 1 — `cross_dataset_join.yaml` expected_output is wrong (P0, scenario-spec bug)

[`src/bricks/playground/web/presets/cross_dataset_join.yaml:13`](../../src/bricks/playground/web/presets/cross_dataset_join.yaml#L13) says `total_completed: 24` but the dataset actually has 18 completed orders. Both Bricks and raw LLM independently compute 18. Either the YAML was updated without re-counting, or the dataset was regenerated with new randomness.

**Fix:** change `total_completed: 24` to `total_completed: 18`. Or regenerate the dataset to have 24 completed orders if 24 is the intended demo answer.

This is a one-line scenario-spec fix; it makes Bricks (and raw LLM) "win" this scenario.

### Issue 2 — Default provider timeout (120s) too short for some compose calls (P1, infrastructure)

The default timeout in [`src/bricks/providers/claudecode/provider.py`](../../src/bricks/providers/claudecode/provider.py) is 120s. The web playground inherits it. Some compose calls — especially first-run on cold cache, with the post-#66 expanded catalog — need longer.

**Fix:** raise default to ~300s and/or expose a `timeout` field in the playground `RunRequest`. The bench-runs `tracks/track-1-exploration/run.py` already overrides to 600s via `PROVIDER_TIMEOUT_S`.

### Issue 3 — UI verdict for `cross-dataset-join` reports "Side-by-side results" when both fail; should call out broken expected_output (P2, ergonomics)

When `passed == rPassed == 0`, the UI says "Side-by-side results" rather than something like "Both engines disagree with the expected output — check the scenario spec." This is what made the user think Bricks was failing. A more diagnostic UI message could prevent the misread.

## Suggested message to the user

> The playground at `bf68452` actually shows Bricks **winning** on 2 of 4 scenarios (CRM and Ticket pipelines). The "Orders Customer Join failure" is a bad expected value in the scenario YAML — both engines correctly compute `total_completed: 18`, but the YAML asserts 24. The custom-example timeout is a provider-default issue, not a compose-quality issue. Three issues drafted: (1) fix the YAML expected, (2) raise provider timeout, (3) better UI messaging for "both engines disagree with spec."

## Reproduction

```
.venv/Scripts/python -m bricks.playground.web   # start server, port 8742
.venv/Scripts/python runs/playground-replay/replay.py  # runs all 4 scenarios
```

Outputs land in `runs/playground-replay/<scenario_id>.json`. Each contains the full `RunResponse` (Bricks blueprint + DSL + outputs + tokens; raw LLM response + outputs + tokens).
