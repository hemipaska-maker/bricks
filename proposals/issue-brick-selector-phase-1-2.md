# Brick selector: classify-then-filter + miss-fallback (Phase 1 + 2)

**Reporter:** RA (bench-runs worktree)
**Sha:** `bf68452`
**Severity:** P1 (the single biggest token-cost lever; unblocks Bricks-beats-raw-LLM at small N)
**Labels:** `feature`, `composer`, `selector`, `p1`

---

## Summary

`BlueprintComposer` currently sends the **entire registry** (~120 bricks, ~25,000 tokens of catalog) to the LLM on every compose. Most of those bricks are irrelevant to the task at hand. Result: compose tokens dominated by catalog noise; raw LLM looks cheaper at small N because it doesn't pay this tax.

The scaffold for a real selector **already exists** — composer takes a `selector` parameter, `BrickQuery` model has the right fields, `SelectionTier` ABC and two concrete tiers (`keyword_tier`, `embedding_tier`) are implemented. Default `AllBricksSelector` just sends everything verbatim.

This Issue: ship the **smallest selector that produces measurable savings**, plus a **fallback path** when the selector picks wrong.

## Goal

After this PR:
- Compose pool size on a typical playground task drops from ~120 to ≤15 bricks.
- Compose total tokens drop from ~25k to ≤4k on first run; ≤1k on warm cache.
- When the classifier guesses wrong, the composer retries with a broader pool and still succeeds.
- Bricks beats raw LLM on token count for the playground's `crm-pipeline` and `ticket-pipeline` scenarios (currently loses by 10–20×; should win or tie).

## Phase 1 — Classify-then-filter

### Architecture

```
task_text
  ↓
[TaskClassifier]  → BrickQuery {categories: [...], tags: [...]}
  ↓
[FilteringSelector]  registry → keep where category ∈ query.categories
                                or any(tag ∈ query.tags)
  ↓
small pool (target 8–15 bricks)  →  composer
```

### Files to add

- `src/bricks/selector/task_classifier.py` — single LLM call. Input: task text + a fixed enum of categories + a fixed enum of tags. Output: `BrickQuery`. Use Haiku by default (it's cheap and the task is simple). Cache the response keyed by `(task_text_fingerprint, registry_version)` so repeated calls are free.

- `src/bricks/selector/filtering_selector.py` — implements `BrickSelector.select(task, registry) -> BrickRegistry`. Internally:
  1. Calls the classifier to get a `BrickQuery`.
  2. Iterates the registry; keeps bricks where `meta.category in query.categories` OR `set(meta.tags) & set(query.tags)`.
  3. Always includes the engine builtins (`for_each`, `branch`, `flow`, plus `extract_json_from_str` since most playground tasks need it).
  4. Returns a sub-registry containing the kept bricks.

- `src/bricks/selector/__init__.py` — export `FilteringSelector`, `TaskClassifier`.

### Wiring

`Bricks.default(...)` already accepts a selector via composer parameter. Add a `selector_type: Literal["all", "filtered"] = "all"` kwarg or just plumb a real selector through. Default behavior unchanged for backward compat; opt-in with `Bricks.default(selector=FilteringSelector())`.

The web playground (`src/bricks/playground/showcase/engine.py:135`) should switch to `FilteringSelector()` once the implementation lands.

### Classifier prompt sketch

```
You are routing a task to a small subset of bricks.

Available categories: data_transformation, math, validation, string_processing,
  io, date, list, dict, ...

Available tags: filter, aggregate, join, sort, count, dedup, parse, format,
  extract, map, reduce, ...

Task: {task_text}

Return ONLY a JSON object: {"categories": [...], "tags": [...]}.
Pick the smallest set that covers the task. Err on the side of more, not fewer.
```

Single LLM call, ~150 in / ~30 out tokens. ~$0.001 on Haiku.

The category/tag enums should be derived from the actual registry's metadata at startup, not hardcoded — so adding a new brick category automatically updates the classifier's choices.

## Phase 2 — Miss fallback

### Trigger

When compose fails with one of:
- `BrickNotFoundError` (registry doesn't have the name the composer used)
- `CompositionError` containing "validation failed" or "unknown step.X"
- Composer emits valid DSL but at execute time the step references an unknown brick

### Strategy

1. Inspect the failure message for the specific brick name `X` the composer wanted.
2. Look up `X` in the **full** stdlib registry (not the filtered pool). Get its `meta.category` and `meta.tags`.
3. Build a broader `BrickQuery` that includes those category+tags.
4. Re-run the selector with the broader query.
5. Recompose with the larger pool.
6. Cap total compose attempts at 2 (one with filtered pool, one broadened). After that, fall back to `AllBricksSelector` for one final attempt. After **that**, surface the failure cleanly.

### Code surface

- `src/bricks/selector/filtering_selector.py` — add `select_broader(self, prior_query, *, missing_brick=None) -> BrickRegistry` that returns a wider pool.
- `src/bricks/ai/composer.py` — wrap compose in a small retry loop that catches the trigger errors and asks the selector to broaden. Do NOT fold this into the existing `HealerChain` — healers are for runtime fixes, this is a compose-stage retry.

### Cost ceiling

- Phase 1 successful compose: 1 classifier call + 1 compose call.
- Phase 2 with one broaden: 1 classifier + 2 compose.
- Worst case (broaden + all-bricks): 1 classifier + 3 compose.

Phase 2 only fires on a real selector miss; should be rare once Phase 1 is tuned.

## Test plan

- **Unit:** classifier on a fixture task returns expected category/tag sets. (Mock the LLM.)
- **Unit:** `FilteringSelector` with a hand-built `BrickQuery` returns the expected sub-registry.
- **Unit:** `FilteringSelector.select_broader` adds the missing brick's category to the prior query.
- **Integration:** Compose `crm-pipeline` task with `FilteringSelector`. Pool size ≤15. Compose succeeds. Outputs match expected.
- **Integration:** Compose a task that needs a brick the classifier didn't pick. First compose fails; broaden; second compose succeeds.
- **Integration:** Compose with the classifier disabled (returning empty query). Falls through to all-bricks. Backward compat preserved.
- **Bench:** Re-run the bench-runs reliability sweep (15 tasks). Bricks success rate should not drop below 10/15. Compose total tokens should drop on at least 12/15.

## Acceptance

- [ ] `Bricks.default(selector=FilteringSelector())` works end-to-end.
- [ ] Compose pool size on `crm-pipeline` drops from ~120 to ≤15.
- [ ] Compose total tokens on first run ≤4,000 (was ~25,000).
- [ ] On warm cache, compose total tokens ≤1,000.
- [ ] On a known classifier-miss task, fallback recomposes with a broader pool and succeeds.
- [ ] Bench-runs reliability sweep: ≥10/15 success (no regression).
- [ ] All new tests pass; CI green on 3.10/3.11/3.12.
- [ ] `Bricks.default()` without `selector=` continues to use `AllBricksSelector` — no breaking change.

## Non-goals (do NOT include in this PR)

- **Embedding-based selection** — Phase 3, separate issue.
- **Tiered scoring with multiple weighted tiers** — Phase 3.
- **Brick package discovery** — Phase 4.
- **Profile-guided pool warming** — Phase 4.
- **Replacing the default selector globally** — keep `AllBricksSelector` as the default for backward compat. Opt-in only for now.

## Files referenced

- [`src/bricks/ai/composer.py`](src/bricks/ai/composer.py) — composer hook point at line 302
- [`src/bricks/core/selector.py`](src/bricks/core/selector.py) — current `AllBricksSelector` and `BrickSelector` ABC
- [`src/bricks/selector/base.py`](src/bricks/selector/base.py) — `BrickQuery` and `SelectionTier`
- [`src/bricks/selector/keyword_tier.py`](src/bricks/selector/keyword_tier.py), [`embedding_tier.py`](src/bricks/selector/embedding_tier.py) — existing tier implementations (not used in this PR; foundation for Phase 3)
- [`src/bricks/stdlib/data_transformation.py`](src/bricks/stdlib/data_transformation.py) — example brick with `tags=`, `category=` already populated
- [`src/bricks/playground/showcase/engine.py`](src/bricks/playground/showcase/engine.py) line 135 — playground engine that would switch selectors

## Why now

The bench-runs research at [`findings.md`](findings.md) shows that on small-N single-run scenarios (which is what every playground demo is), Bricks loses to raw LLM on tokens by ~10–20× because of catalog overhead. Fixing this puts Bricks ahead at every regime, not just N≥200. The scaffold is already half-built; this PR finishes it.
