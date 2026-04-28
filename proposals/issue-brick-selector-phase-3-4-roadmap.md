# Brick selector: tiered scoring + package discovery (Phase 3 + 4 roadmap)

**Reporter:** RA (bench-runs worktree)
**Sha:** `bf68452`
**Type:** Tracking issue / roadmap
**Severity:** P2 (compounding wins, not the headline)
**Labels:** `enhancement`, `tracking`, `composer`, `selector`, `roadmap`

---

## Summary

This is the **roadmap follow-on** to the Phase 1+2 selector PR (filtering + miss-fallback). Once a basic filtered selector is shipped, the remaining wins come from making the selector **smarter** (Phase 3) and **extensible** (Phase 4).

Treat this as a tracking issue. Each phase below should spawn its own implementation Issue when it gets prioritized — don't merge them. The point of this doc is to keep the long-run shape coherent so Phase 1+2 doesn't paint us into a corner.

## Phase 3 — Tiered scoring with embeddings

### Why

The Phase 1 classifier is a single LLM call returning a flat `BrickQuery {categories, tags}`. It works for tasks whose vocabulary aligns with the brick metadata. It misses when:

- A task says "deduplicate" but the matching brick is `unique_dict_list` (no `dedup` tag).
- A task says "merge two lists" but the matching brick is `join_lists_on_key` (tagged `join`, not `merge`).
- A task is genuinely ambiguous and could be served by bricks across 3+ categories.

A scoring approach handles all three: rank every brick by *how well it matches the task* and take top-K, instead of a binary include/exclude.

### Architecture

The scaffold for this **already exists** in [`src/bricks/selector/`](src/bricks/selector/):
- `BrickQuery` (full set of fields, not just categories+tags from Phase 1).
- `SelectionTier` ABC: `score(query, name, meta, callable_) -> float ≥ 0`.
- `keyword_tier.py` — implemented.
- `embedding_tier.py` — implemented.

What's missing: a `TieredBrickSelector` that combines tiers and selects top-K.

```
TieredBrickSelector(tiers=[KeywordTier(weight=0.4),
                            TagCategoryTier(weight=0.3),
                            EmbeddingTier(weight=0.3)],
                    top_k=12)
   .select(task, registry)
```

For each brick:
- Each tier returns 0.0–1.0.
- Combined score = Σ(tier_weight × tier_score).
- Keep top K bricks by combined score.
- Always include engine builtins (`for_each`, `branch`, `flow`).

### Embedding setup

- Compute brick embeddings once at registry construction (or at first `.select()` call). Cache them by (brick name, registry version).
- Compute task embedding per `.select()` call. Cheap on Haiku-class embedding models.
- `EmbeddingTier.score(query, ..., meta) = cosine(task_embed, brick_embed)`.

The cost of embeddings amortizes across many compose calls — far below the 25k-token catalog tax we're saving.

### Tunability

Different task families benefit from different tier weights. Expose:

```python
TieredBrickSelector(
    tiers=[...],
    weights=lambda task_family: ...,  # optional, defaults to uniform
    top_k=12,
)
```

If the user has prior knowledge ("my agent does data joins, not text generation"), they can configure heavier weight on `TagCategoryTier`.

### Acceptance for Phase 3

- [ ] `TieredBrickSelector` working with the three implemented tiers.
- [ ] Embedding tier reduces miss rate on the bench-runs reliability sweep (compared to Phase 1 classify-then-filter alone).
- [ ] No regression in compose token count vs Phase 1.
- [ ] Top-K is configurable; default K=12.

## Phase 4 — Long-run capabilities

These four are roadmap items, not a single PR. Each gets its own Issue when prioritized.

### 4.1 Brick package discovery

When the selector returns an empty (or near-empty) pool for a real task, it's a signal that **no installed pack covers this domain**. Today the user gets a confusing compose failure. Better:

- Maintain a registry of known installable packs (`bricks-stdlib`, `bricks-finance`, `bricks-text`, `bricks-images`, ...). Each pack publishes its category/tag manifest.
- When the selector misses, query the manifest registry: "tasks like this often need bricks from `bricks-text`. Install? (y/n)"
- **Never auto-install.** Surface the suggestion; let the user/agent decide.

This becomes the equivalent of npm/cargo's "did you mean to install this package?" UX.

### 4.2 Cross-category queries

Some tasks need bricks from multiple unrelated categories (e.g. parse-XML + arithmetic + emit-CSV). Phase 1's OR filter handles this; Phase 3's scoring handles it better. But complex tasks may need a stronger guarantee:

> "must include bricks from each of [parse, math, format]"

Add a `must_include_categories: list[str]` to `BrickQuery`. The classifier (or a separate planner) populates it for compound tasks. The selector enforces "at least one brick from each category" rather than top-K-globally.

### 4.3 Interactive refinement on miss

Today: compose fails → error message → user re-types the task and hopes.

Better: when compose fails with a missing-brick or selector-empty-pool signal, the agent surfaces:

> "I tried bricks A, B, C. The gap was: I needed something that does X but couldn't find it. Options:
>   1. Install package `bricks-text` (has 8 string-similarity bricks).
>   2. Reword the task to avoid X.
>   3. Add a custom brick for X."

This is a UX layer on top of the selector + miss fallback, not a selector feature itself. Worth its own design pass.

### 4.4 Profile-guided pool warming (PGO)

Inspired by `gcc -fprofile-use`. Track which bricks the composer actually USES per task family across many runs:

- Per blueprint in the store, log the bricks that ended up in the final blueprint.
- For task families with ≥N runs, pre-build a "hot pool" of just-the-used-bricks.
- On the next compose for that family, skip the classifier entirely and use the hot pool directly. Compose is now a pure cache-warm read.

This is the equivalent of "compile once, then JIT-tune for the hot path" — and it'd give Bricks the **"gets better with use"** narrative the article notes call out.

### 4.5 Brick aliases / deprecation

When `count_dict_list` is renamed `count_records`, the selector handles the alias. The composer never sees the old name. Provided by metadata:

```python
@brick(tags=[...], category=..., aliases=["count_dict_list"])
def count_records(...): ...
```

Selector queries match against current name AND aliases. Compose-time validation rejects deprecated direct usage. Migrations stop being painful.

## How these connect to the article

The selector improvements directly map to compiler-theory improvements that already appear in [`article/notes-composer-as-compiler-improvements.md`](article/notes-composer-as-compiler-improvements.md):

| This roadmap | Compiler equivalent |
|---|---|
| Tiered scoring (Phase 3) | Optimization passes / heuristic-driven selection |
| Embedding tier | Static analysis with semantic similarity |
| Package discovery (Phase 4.1) | `apt-get install missing-dev` on link error |
| PGO pool warming (Phase 4.4) | `gcc -fprofile-use` |
| Aliases (Phase 4.5) | Symbol versioning / API ABI |

The article can frame the selector as **"`#include` for the LLM-as-compiler model"** — without it, every compile pulls in the entire stdlib like a C program that `#include`s every header in `/usr/include/`.

## Tracking checklist

- [ ] Phase 1+2 PR merged (separate Issue: filter + miss fallback).
- [ ] Phase 3.1 — Wire `TieredBrickSelector` (existing tiers, no embeddings yet).
- [ ] Phase 3.2 — Add embedding setup + `EmbeddingTier` integration.
- [ ] Phase 3.3 — Tunable weights, default tuning.
- [ ] Phase 4.1 — Package manifest registry + miss-time suggestion UX.
- [ ] Phase 4.2 — `must_include_categories` semantics.
- [ ] Phase 4.3 — Interactive refinement UX (separate design doc first).
- [ ] Phase 4.4 — PGO pool warming hooked into the blueprint store.
- [ ] Phase 4.5 — Brick aliases in metadata + selector-side handling.

## Out of scope for this tracking issue

- Re-architecting the brick metadata format. Keep `tags`/`category`/`destructive`; just add `aliases` (Phase 4.5) when needed.
- Replacing `BlueprintComposer`'s API. The selector hook is the only contract; everything else is internal.
- Multi-language brick packs. Stay in Python for now.

## Why this matters

Phase 1+2 is a **token-cost** win at small N (~10–20× saving). Phases 3+4 are **reach** wins: they let Bricks handle tasks the user didn't anticipate when picking a stdlib version, and they let the system **improve over time**. The article's "software that gets better with use" narrative is paid by Phase 4.4 specifically — until that ships, every Bricks instance starts cold and stays cold.

This roadmap should NOT be merged as one PR. The point of writing it down is to make sure Phase 1+2's API doesn't accidentally close any of these doors.
