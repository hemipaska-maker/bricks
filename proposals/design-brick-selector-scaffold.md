# Design proposal — Brick selector: from "send everything" to a real catalog filter

**Status:** RA proposal, ready to harden into an Issue
**Sha:** `bf68452`
**Driver:** Compose currently sends ~120 bricks (~25k tokens of catalog) to the LLM on every task. Scaling task complexity ≠ scaling catalog size, so most of those tokens are noise. A working selector would cut compose tokens 10× and put Bricks ahead of raw LLM at small N too.

---

## Where we are today

Two halves already exist; they're just not wired together.

**Half 1 — composer hook point** ([`src/bricks/ai/composer.py:23, 269, 302`](src/bricks/ai/composer.py)):

```python
class BlueprintComposer:
    def __init__(self, ..., selector: BrickSelector | None = None, ...):
        self._selector = selector or AllBricksSelector()
        ...
    def compose(self, task, registry, ...):
        pool = self._selector.select(task, registry)   # ← swap the selector, swap the pool
```

Default `AllBricksSelector` returns the whole registry verbatim. Done deal.

**Half 2 — query model + tier ABC + two real tiers** ([`src/bricks/selector/`](src/bricks/selector/)):

- `BrickQuery`: `categories`, `input_types`, `output_types`, `tags`, `keywords` — structured fields any tier can score against.
- `SelectionTier` ABC with one `score(query, name, meta, callable_) -> float` method.
- `keyword_tier.py`, `embedding_tier.py` — already implemented but un-exercised.

Every brick in stdlib is already decorated with `tags=[...], category="..."` ([example: `join_lists_on_key`](src/bricks/stdlib/data_transformation.py#L297)). The metadata is sitting there.

**What's missing:** a wiring layer that takes a natural-language task and produces a small relevant pool by routing through tiers.

## Phase 1 — Minimum viable: classify-then-filter (1-2 days)

The smallest thing that produces measurable token savings.

### Architecture

```
task_text
  ↓
[classifier]  → BrickQuery {categories: [...], tags: [...]}
  ↓
[FilteringSelector]  iterate registry, keep bricks where
                      brick.category ∈ query.categories
                      OR  any(tag ∈ query.tags)
  ↓
small pool (target: 8-15 bricks)  →  composer
```

### How the classifier works (Phase 1, dumb-but-cheap)

A single small LLM call **before** compose:

```
You see a task description and a list of brick categories.
Return JSON: {"categories": [...], "tags": [...]}.

Categories: data_transformation, math, validation, string_processing, ...
Tags: filter, aggregate, join, sort, count, dedup, ...

Task: {task_text}
```

Output: `{"categories": ["data_transformation", "math"], "tags": ["join", "filter", "aggregate"]}`. Tens of tokens, costs ~$0.001 on Haiku.

Then the FilteringSelector keeps any brick where category matches OR any tag overlaps. ~10 bricks for a typical task.

### What we save

- Compose prompt: ~25k → ~3k tokens (catalog goes from 120 bricks to ~10).
- One extra LLM call (~$0.001).
- Net: Bricks compose at ~$0.005 cold, near-zero warm. **Beats raw LLM on tokens at N=50, not just N=200.**

### Code surface

- `src/bricks/selector/filtering_selector.py` — new file or finish the existing `core/filtering_selector.py` if usable.
- `src/bricks/selector/task_classifier.py` — new; the small LLM call.
- One unit test fixture that asserts task "sum the values" → query containing categories/tags that include `reduce_sum`.
- Composer constructor signature unchanged (just plumb the new selector through `Bricks.default(selector=...)`).

### Failure mode

If the classifier picks wrong categories, the composer doesn't see the brick it actually needs and **fails or hallucinates a brick name**. We need a fallback (Phase 2).

## Phase 2 — Fallback on miss (~1 day)

Catch the "brick not found" / "compose failed validation" path and **re-select with a broader query**.

### Architecture

```
selector.select(task)  →  pool_v1  →  compose  →  fail (missing brick / KeyError)
                                                     ↓
                                          inspect failure mode:
                                          "X" not found → add tags/categories that contain X
                                                     ↓
                                          selector.select_broader(task, hint=X)  →  pool_v2  →  recompose
```

### Triggers for broadening

- `BrickNotFoundError`: the composer used a brick name that exists in the full registry but not in the pool. Add the brick's category to the query, retry.
- AST validator says "unknown step.X(...)": same as above.
- Compose succeeds but execution fails on a type mismatch where the right brick exists in another category: flag for the next-level fallback (Phase 3).

### Cost ceiling

Cap retries at 2. If compose still fails with the broader pool, fall back to `AllBricksSelector` for one final try. After that, surface the failure cleanly.

## Phase 3 — Tiered scoring + embeddings (~1-2 weeks)

Use the existing `SelectionTier` ABC seriously.

```
TieredBrickSelector
  ├── KeywordTier        score by name/description match (cheap, deterministic)
  ├── TagCategoryTier    score by query.tags ∩ brick.tags  (cheap, deterministic)
  ├── EmbeddingTier      score by cosine(task_embed, brick_embed)  (one-time embedding setup)
  └── reduce by max-or-sum  → top-K
```

Each tier returns 0.0–1.0. Selector keeps top K=10 by combined score.

This makes the selector **tunable**: you can dial up keyword weight when tasks are precise, up embedding weight when tasks are vague.

`EmbeddingTier` is the unlock for "semantically similar but tag-different" — e.g. task says "deduplicate" but the relevant brick is `unique_dict_list` (no `dedup` tag). Embeddings catch this; tags don't.

## Phase 4 — Long-run scaffold (months, not days)

The Phase 1 selector is a flat lookup. Real production needs:

1. **Brick package discovery.** When the selector doesn't find anything that satisfies the query, query a registry of installable packs (`bricks-stdlib`, `bricks-finance`, `bricks-text`, ...) and surface "install bricks-text? It has 8 string-similarity bricks that match this task." Don't auto-install — surface and let the user/agent decide.

2. **Cross-category queries.** Some tasks need bricks from multiple unrelated categories (e.g. parse-XML + arithmetic + emit-CSV). The Phase-1 OR filter handles this; Phase-3 scoring handles it better. But we need a "must-include from each of these categories" semantics for harder tasks.

3. **Interactive refinement.** When compose fails repeatedly:
   - Show the user "the composer tried bricks A, B, C; the gap was X. Suggest brick D? Install pack Y?"
   - This is an agent-loop UX, not just a selector.

4. **Profile-guided pool warming.** Same pattern as PGO in compilers (see [article/notes-composer-as-compiler-improvements.md](article/notes-composer-as-compiler-improvements.md)). Track which bricks the composer actually USES per task family. Pre-warm pools for hot task patterns.

5. **Brick deprecation / aliasing.** If `count_dict_list` is renamed `count_records`, the selector handles the alias. The composer never sees the old name.

## Recommended issue scope

**File one Issue for Phase 1 + Phase 2.** They're a coherent unit: filter, fall back when filter is wrong. Delivers the headline win (Bricks beats raw LLM on tokens at N=50).

Phases 3 and 4 are roadmap items — mention them in the Issue's "future work" but don't block on them.

## Acceptance for Phase 1+2

- [ ] `Bricks.default(selector=TaskClassifierFilteringSelector())` works.
- [ ] On the playground's `crm-pipeline` scenario, compose pool size drops from ~120 to ≤15 bricks.
- [ ] Compose total tokens drop from ~25k to ≤4k on first run, ≤1k on warm cache.
- [ ] When the classifier picks wrong categories, fallback re-selects and compose succeeds.
- [ ] No regression in the bench-runs reliability sweep (Bricks 10/15 → still ≥10/15 with the new selector).

## Article connection

This proposal directly answers the article's open question: *"why is Bricks compose so big?"* It's not the data; it's the catalog. The compiler analogy makes it obvious — a real compiler doesn't load every header file in `/usr/include` for every translation unit. It includes only what's referenced.

The brick selector is **`#include` for the LLM-as-compiler model.** Without it, Bricks pays for headers it never used. With it, the structural win extends down to N=50, and the article's tipping point graph crosses earlier.
