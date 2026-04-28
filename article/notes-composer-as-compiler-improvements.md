# If the composer is a compiler, what's it missing?

Real compilers are 60+ years of engineering. Bricks' composer is one LLM call + an AST whitelist. Here's the gap, ordered by leverage. Each item maps to a real compiler technique.

## Tier 1 — easy wins, big payoff

These are mostly *about not regressing on what the LLM emits*. Cheap to add, would prevent half our bug reports.

### 1. Type-check brick output → next brick input

A real compiler verifies that `f(x: int)` doesn't get called with a string. Bricks has a registry with input/output schemas. Use them.

Today: composer emits `step.calculate_aggregates(items=wrapped.output, field="v")`. If `wrapped.output` is a list of `[float]` instead of `[dict]`, this fails at runtime with `KeyError`. Compiler-style: catch this at compose time, report `step 3: calculate_aggregates expects items=list[dict[str, num]], got list[float] from step 1`.

**Win:** every Bug B-style "blueprint composes but blows up at exec" becomes a compose-time error.

### 2. Diagnostics with line numbers and step IDs

Real compilers say: `error: at line 4, column 23: expected expression`.

Bricks today says: `Brick not found: '__for_each__'` — useless for figuring out *which* step in a 6-step blueprint.

Each blueprint step already has an ID (`step_1_reduce_sum`). Surface it everywhere. Add the source line from the LLM-generated DSL when validation fails.

**Win:** debug time drops 5×. A real compiler that raised `ValueError` with no source location would be unshippable.

### 3. Strict DSL grammar before exec

Today: `validate_dsl(code)` checks AST whitelist, then `exec(code, namespace)` runs it. The validator catches "no imports allowed" but not "your `for_each(do=lambda)` calls a brick with wrong kwargs."

Add a stricter grammar pass between AST validation and exec:
- Every `step.X(...)` call resolves to a real brick.
- Every kwarg matches the brick's signature.
- Every `for_each(do=...)` lambda body is a single `step.X(...)` call.
- Output type of step N is compatible with input type of step N+1.

**Win:** Bug A and Bug B both get caught at compose time, no `$1.25 burn → mysterious runtime crash`.

## Tier 2 — medium effort, real lift

### 4. Optimization passes on the Node graph

The Node graph (in `dsl.py`) is the IR — like LLVM IR. You can run multiple passes over it before code-gen:

- **Dead code elimination:** drop steps whose outputs aren't read. (Composer sometimes emits debug intermediates the LLM "thought about.")
- **Constant folding:** if a step's args are all literals and the brick is pure, run it at compile time, replace with the result.
- **Common subexpression elimination:** `step.parse_date(d)` called twice with the same `d` → run once, reuse.
- **Specialization:** generic `step.calculate_aggregates(operation="sum")` → specialized `step.reduce_sum`. Skips dispatch.

**Win:** smaller, faster blueprints. More importantly: every composed blueprint becomes the *same* blueprint after canonicalization, which improves cache hit rate (different LLM phrasings of the same task converge to one normalized IR).

### 5. Profile-guided optimization (PGO)

Real compilers (`gcc -fprofile-use`) take runtime stats and re-optimize hot paths. Bricks could:

- Track per-blueprint exec count + latency in the store.
- For blueprints that ran 100+ times, kick off a "re-compile" pass: feed the *original task + the current blueprint + observed runtime data* back to the LLM, ask it to optimize. Result replaces the cache entry.
- Hot blueprints get smaller and tighter over time without user intervention.

**Win:** Bricks gets *better* the more it's used. Inverse of LLM agents that get worse-or-stay-same.

### 6. Compile modes — `-O0` vs `-O2`

`gcc -O0`: fast compile, slow code. `gcc -O2`: slow compile, fast code.

Today: every Bricks compose is the same. One model, one prompt, one pass.

Could expose:
- **`compile_mode="draft"`** — Haiku, single pass, $0.005, takes 5s. Good for prototypes.
- **`compile_mode="release"`** — Opus or Sonnet + multi-pass optimizer + self-check, $0.20, takes 60s. Good for blueprints you'll run a million times.

Promote draft → release automatically when a draft blueprint hits 100 runs.

**Win:** users pay for compose proportional to how much they'll reuse. The 99% of one-off tasks stay cheap; the 1% that matter get tight.

## Tier 3 — bigger architectural shifts

### 7. Self-consistency / multi-vote for determinism

LLMs are stochastic; same task → slightly different blueprints. The blueprint store memoizes this, but the *first* compose is whichever variant the LLM happened to emit.

Compiler-style fix: compose **N times**, pick the blueprint that:
- Appears most often (deterministic-by-majority), OR
- Passes the most validation checks, OR
- Compiles to the smallest IR.

Cost: N× the compose tokens. Done once per task; amortizes immediately.

**Win:** blueprints converge to a canonical form. Two users typing slightly different prompts for the same task get the same blueprint.

### 8. Hierarchical composition — a module system

Today: every blueprint is monolithic. A 12-step blueprint with a 5-step sub-pattern that appears in 50 other blueprints duplicates that 5-step block 50 times.

Compiler-style fix: blueprints can `import` other blueprints. The composer learns to factor common sub-patterns into named, reusable sub-flows.

This is **static linking** for blueprints. Or, for the cool kids: **a build system on top of the brick catalog**.

**Win:** smaller blueprints, better cache reuse, shared sub-flow optimizations propagate. Also: opens the door for community-contributed sub-flows.

### 9. AOT vs JIT modes

`Bricks.compile(task) → Blueprint` (AOT — explicit; user freezes the artifact, ships it, runs it forever).
`Bricks.execute(task, inputs)` (JIT — current behavior; compose-on-miss, exec, cache).

AOT mode is what you want for production deploys: compose offline, code-review the blueprint, ship the YAML alongside your code, never invoke the LLM in prod.

**Win:** removes LLM cost and latency from prod entirely. Compliance-friendly. Auditable diffs in PRs ("this blueprint changed; here's the new YAML").

### 10. Make compilation deterministic by construction

Set composer LLM to `temperature=0`, force JSON output mode for the structured fields, hash the prompt + catalog version into the cache key. Same input → same blueprint → same hash → cache hit.

Today the cache hits because the blueprint *fingerprint* matches, but two slightly different task prompts that mean the same thing miss the cache. Determinism plus a normalization pass on the task input would let "sum the values" and "compute the sum of values" hit the same cache entry.

## What this section gives the article

The compiler framing isn't just rhetoric — it produces a **concrete roadmap**. Every item above is a known compiler technique applied to a real Bricks weakness. The article can:

1. Argue the LLM-as-compiler thesis (the framing).
2. Show our failed-and-recovered probes (the data).
3. Project forward: here's what a *mature* LLM-as-compiler looks like (this list).

That third part is what differentiates the article from a marketing piece. We're not saying "Bricks is great," we're saying "Bricks is the v0.5 of a category, and the category has 50 years of compiler theory waiting to be applied."

## Pick-list — what RA would propose first as Issues

If we wanted to feed the next sprint, in order:

1. **Type-check brick I/O at compose time** (Tier 1 #1) — biggest "fix the bug class" lever
2. **Step-IDs in error messages** (Tier 1 #2) — biggest "fix the dev-loop" lever
3. **Strict DSL grammar before exec** (Tier 1 #3) — would have caught Bug A and Bug B both
4. **DCE + specialization passes on the Node IR** (Tier 2 #4) — modest, sets up everything else
5. **PGO with run counts in the store** (Tier 2 #5) — the "Bricks gets better with use" story is *very* article-friendly

Items 6–10 are research-grade — call them out in the article's "future work" section.
