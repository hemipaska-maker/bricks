# Your LLM Agent Is Melting Cash

*Draft v1 — full article, ~1,500 words. For engineers building agent pipelines.*

---

## The squared-sum incident

I gave Claude Sonnet 4.6 a task: take a list of 50 numbers, square each one, sum the squares.

It produced a 50-row markdown table.

```
| #  | Value    | Squared   |
|----|----------|-----------|
| 1  | 56.4915  | 3191.2896 |
| 2  | 58.885   | 3467.4432 |
| 3  | 12.016   | 144.3843  |
...
```

Then summed in five groups of ten. Then added the group totals. Then declared the answer: **123,300.1025**.

The correct answer was **123,300.1125**. A tenth of a percent off — close enough that a casual reader would miss it, and exactly wrong if you're billing customers or balancing a ledger.

The call took 11 seconds and cost $0.46. Run that math in plain Python (`sum(v*v for v in values)`): exact answer, half a second, $0.04.

The LLM was *trying* to do arithmetic in tokens. Rendering computation as text and reading the text back. We've built an interpreter where we should have built a compiler.

---

## Most agents are interpreters

Look at how agent frameworks work today. A user request comes in. The LLM decides what to do. It calls a tool. The tool returns. The LLM decides the next step. Another tool call. Another decision. Each step pays the LLM tax: round-trip latency, output tokens, attention budget, billing meter ticking.

Run that pipeline twice and the LLM does the same work twice. Run it a million times and it does the same work a million times. The pipeline never gets cheaper, faster, or more reliable. Every word the model emits is a fresh decision, made under the same uncertainty, billed at the same rate.

This is exactly how a tree-walking interpreter executes a program: re-parse the source, re-resolve every name, re-decide every branch, every single run.

```
┌─── Interpreter mode (current LLM agents) ────────────────┐
│                                                          │
│  request ──► LLM ──► tool ──► LLM ──► tool ──► LLM ──►   │
│              ▲       │        ▲       │        ▲         │
│              └───────┘        └───────┘        │         │
│             $$$ each call. Non-deterministic. Slow.      │
└──────────────────────────────────────────────────────────┘

┌─── Compiler mode (what we want) ─────────────────────────┐
│                                                          │
│  request ──► LLM (once) ──► blueprint (cached, deterministic) │
│                                  │                       │
│                                  ▼                       │
│                            run, run, run...              │
│                            ~$0 per run, exact, fast      │
└──────────────────────────────────────────────────────────┘
```

The LLM is good at *semantic translation* — parsing fuzzy intent into structured operations, picking the right primitive for a job, composing five steps into a coherent plan. It is bad at *mechanical execution* — running a plan a thousand times without drifting, counting, doing arithmetic in the output stream, holding 1,000 floats in attention.

**Use the LLM where it's strong. Cut it out of the loop where it isn't.** That's a compiler.

A compiler does five things:

| Stage | Compiler | LLM-as-compiler (Bricks-style) |
|---|---|---|
| Parse | Read source | LLM reads natural-language task |
| Resolve | Look up symbols, types | Brick catalog → primitives matching intent |
| Optimize | Prune, fuse | Composer picks right reducer, drops dead steps |
| Code-gen | Emit machine code | Emit deterministic blueprint (YAML / Python flow) |
| Cache | Build artifact, link | Blueprint store: same task → same artifact |

This isn't analogy stretched to fit. The architecture maps. The cost curves below fall directly out of it.

---

## What the data says

I ran a sum task at four sizes (N=50, 200, 1,000, 5,000), against two engines (raw LLM, and a Bricks-style compiler/runtime), on two models (Sonnet 4.6 and Haiku 4.5).

```
Cost per run, log scale ($)

  $1.00 │
        │
  $0.30 │       ●━━━━ R-Sonnet     ✗  ✗
        │      ╱        ✗ TIMEOUT
  $0.10 │     ╱      ●━ R-Haiku     ✗
  $0.05 │  ●─        WRONG       WRONG
        │
  $0.02 │  ▣━━━━━━━━▣━━━━━━━━▣━━━━━━━━▣  Bricks-Sonnet
  $0.01 │  ▢━━━━━━━━▢━━━━━━━━▢━━━━━━━━▢  Bricks-Haiku
        └──┴──────┴────────────┴────────┴──
           50    200          1000     5000     N
```

The actual numbers:

| N | Bricks-Sonnet | Bricks-Haiku | Raw-Sonnet | Raw-Haiku |
|---|---|---|---|---|
| 50 | $0.189 ✓ | $0.040 ✓ | $0.046 ✓ | $0.033 ✓ |
| 200 | $0.018 ✓ | $0.007 ✓ | $0.298 ✓ | $0.048 **✗** |
| 1,000 | $0.018 ✓ | $0.006 ✓ | **timeout** | $0.117 **✗** |
| 5,000 | $0.018 ✓ | $0.006 ✓ | **timeout** | **timeout** |

Three things to notice:

1. **Bricks lines are flat.** Cost is dominated by compose, not data size. From N=200 onwards, the LLM call is a 30k-token prompt-cache hit; the rest is plain Python `sum()`. ~$0.018 per run on Sonnet, ~$0.006 on Haiku, regardless of how many numbers you throw at it.

2. **Raw-LLM lines climb steeply, then crash into a wall.** Raw Sonnet times out past N=1,000. Not "slower and more expensive" — it literally doesn't return inside 600 seconds. Raw Haiku starts returning *wrong answers* at N=200 (off by exactly 1.0; one number missed). The cheaper model fails earlier.

3. **The tipping point lands around N≈100.** Past that, every additional row of input data widens the gap between the two architectures, until the architectures stop being comparable at all.

For typical agent workloads — invoice extraction, log triage, customer-support classification, daily reports — N is in the thousands or tens of thousands. The right side of this chart is the production regime.

### A note on prompt caching

The Bricks line isn't flat by magic. It's flat because Anthropic's prompt cache absorbs the system-prompt + brick-catalog (~30k tokens), and the only per-call variable is the task description. There are three regimes worth knowing:

- **Session-cold** (first compose ever): pay $0.19 to write the cache.
- **Task-cold** (catalog warm, new task): pay $0.08 — only task-specific tokens are fresh.
- **Task-warm** (re-running same task): pay $0.018 — pure cache reads.

A real production system stays mostly in the third regime, occasionally falling to the second when a new task type hits.

---

## Bit-identical determinism

Same task, run ten times, separate processes. Bricks output: byte-identical across all 10 runs. Same trailing IEEE 754 noise (`6228.260100000002` ten times in a row). Same blueprint YAML emitted by the composer. Same answer.

Raw LLM was also identical in *answer* this time (lucky), but **cost varied 2× across runs** — $0.22 to $0.43 — depending on how warm Anthropic's cache happened to be when each call landed.

If you're shipping anything that has to produce the same answer twice — billing, compliance, regression tests, audit trails — this matters more than the cost curve. Bricks is bit-identical on both axes: answer and cost. Raw LLM is approximately-identical on the answer and lottery-priced on the cost.

---

## Where Bricks loses

Honest section. I gave Bricks a task: rewrite this angry customer email in a warmer tone.

Input: *"hi support, your product STOPPED WORKING after the last update. I've been a customer for 3 years and this is unacceptable..."*

**Bricks output:** the same email, verbatim. No rewriting. The composer found no "rewrite politely" brick in the catalog, so it emitted a no-op pass-through. Cost $0.061.

**Raw LLM output:** *"Hello Support Team, I hope you're doing well. I wanted to reach out regarding an issue I've encountered since the most recent update — unfortunately, the product has stopped working on my end..."* — preserved every fact, kept the order number, nailed the tone shift. Cost $0.022.

Bricks was **3× more expensive AND silently produced the wrong output**. The compiler analogy makes this predictable: a compiler can only emit instructions in its target ISA. If "rewrite politely" isn't in the brick catalog, the composer emits a no-op.

The reliability sweep across 15 diverse short tasks (filters, sorts, top-K, dedup, string ops, dict-field extraction, single reductions) confirms it:

```
                    Bricks  Raw-LLM
sum-only             ✓        ✓
min-only             ✓        ✓
count-gt50           ✓        ✓
sum-gt50             ✗ type   ✓
count-lt10           ✓        ✓
top3-desc            ✓        ✓
bottom3-asc          ✗ Nones  ✓
squared-sum          ✓        ✗ off-by-0.01 ←
median-only          ✓        ✓
range-stats          ✓        ✓
string-lengths       ✗ wrap   ✓
string-uppercase     ✗ wrap   ✓
string-join          ✓        ✓
extract-names        ✓        ✓
dedup-count          ✓        ✓
sort-asc-unique      ✗ type   ✓
                    ────     ────
                    10/15    14/15
                    (66%)    (93%)
```

At small N on one-off tasks, raw LLM is more reliable. The cost-curve win starts at N≥200, not N=50.

The **one** raw-LLM failure is the squared-sum from the opening — and that one Bricks won, exactly because deterministic Python doesn't make markdown-table arithmetic mistakes. That's the wedge.

---

## The 5 Bricks failures, in compiler terms

- **2× type mismatches at brick I/O** (`list` passed to a brick expecting `list[dict]`). A compiler with static type checking on its IR would catch this at compose time, not runtime.
- **2× field-pluck missing.** Composer picked a brick whose output is a wrapper dict (`{"result": "APPLE"}`) and forgot to pluck the field. A canonicalization pass over the IR would normalize this.
- **1× broken chain producing `None`-pollution.** Dataflow validation on the IR would reject this before exec.

Every failure is a known compiler problem. That's the whole point: Bricks today is the v0.5 of a category that has 50 years of compiler theory ready to be applied.

---

## What this means if you're building one

```
Brick catalog        =  ISA
Composer             =  front-end
Blueprint store      =  build cache
Blueprint YAML       =  IR
Engine               =  runtime
```

Five takeaways for engineers:

1. **Design brick libraries like ISAs**, not APIs. Small, orthogonal, composable. The composer's job gets easier as the catalog gets more "ISA-shaped."
2. **Caching is non-negotiable.** Without a persistent blueprint store, you're a JIT — better than an interpreter, but still re-compiling. Persistent cache is what makes the model deterministic in practice.
3. **Validation matters more than generation.** AST whitelist, type checking, grammar pass on composer output. Reject malformed blueprints at compose time, not at execute time burning $1.25 per failure.
4. **Agents become hybrid.** Compiled paths for the known cases. The LLM only re-engages for genuinely novel queries — exactly like a JIT falling back to its interpreter on cold paths.
5. **AOT mode is your production deploy.** Compose offline, code-review the YAML, ship it alongside your code, never invoke the LLM in prod. Compliance-friendly. Reviewable diffs.

---

## The thesis

The LLM-agent industry is treating compilation problems as interpretation problems. Every API call is the LLM "running" the user's intent from source. The cost curves don't lie. The wall at N=1,000 doesn't lie. The 2× cost variance for the same prompt doesn't lie. The squared-sum's 50-row markdown table really happened.

There is an alternative. Compile the intent once into deterministic, auditable, replayable code. The cost curves, the determinism, the auditability — all fall out of one design choice:

**Stop asking the LLM to re-derive the answer. Ask it to write the program once.**

---

*All numbers in this article are from `findings.md` and `manifest/track-1.jsonl` in the Bricks bench-runs worktree, sha `bf68452`. Reproduction: `python tracks/track-1-exploration/run.py --case sum-only --size 200 --model sonnet`.*
