# Article notes — "The LLM should be a compiler, not an interpreter"

*Status: thesis draft. Not yet edited for publication.*

## The framing in one line

For agent workflows that must be reproducible and cheap at scale, **the LLM should be a compiler, not an interpreter.**

## Bricks' value proposition (the saved version)

Bricks ≠ "smarter LLM." Bricks = "freeze the LLM's decisions into reusable code."

The key insight: an LLM call is non-deterministic, slow, and expensive *every time*. Code is deterministic, fast, and free *every time*. Bricks pays the LLM cost **once** to compose a blueprint, then runs it as plain code forever after.

**Who benefits:**
- Devs building agents that need to produce *the same answer twice* (compliance, billing, regression-tested pipelines).
- High-volume workflows where the LLM cost dominates.
- Anyone who wants their agent's behavior to be **auditable** — you can read the blueprint YAML, no black box.

**What Bricks adds over "just have the LLM write Python":**
- A vetted catalog of safe primitives (no random `os.system`).
- Blueprint store — same task → same code, no re-composing.
- AST-validated, exec'd in a restricted namespace.

**Where the data fits:**
- Sonnet raw at N=1000: 💥 timeout, non-deterministic
- Gemini-with-tools at N=1000: ✓ but you pay the LLM every call
- Bricks at N=1000: ✓, $0.02, **same answer every time**

The third row is the wedge.

## Why "compiler" isn't just a metaphor

A compiler does five things: parse, resolve, optimize, code-gen, cache. Bricks does **literally these five things** with an LLM as the front-end:

| Compiler stage | Bricks equivalent |
|---|---|
| Parse source | LLM reads natural-language task |
| Resolve symbols | Brick catalog → which primitives map to which intent |
| Optimize | Composer prunes branches, picks the right reducer |
| Code-gen | Emit deterministic blueprint (YAML/Python flow) |
| Build cache | Blueprint store: same task → same artifact, no re-compile |

The architecture maps. That's why the metaphor is sticky.

## What "compile" actually buys you

**Interpreters re-decide everything every run.** Every word the LLM emits is a fresh decision: which tool to call, which order, how to parse the input. Stochastic, slow, expensive — every single time.

**Compilers decide once.** All the planning happens at compile time. At runtime, you just execute. Deterministic, fast, ~free.

The LLM is *good at* compilation work — disambiguating intent, picking primitives, chaining steps. It's *bad at* interpretation work — running the same loop a million times without drifting.

**Use the LLM where it's strong (semantic translation), cut it out of the loop where it's weak (mechanical execution).**

## The economic shape

In compiled languages, most operations cost ~0 at runtime. The cost is amortized into compilation. Same here:

```
Interpreter mode (current LLM agents):   cost = N_runs × LLM_call_cost
Compiler mode (Bricks):                  cost = 1 × LLM_call_cost + N_runs × ~0
```

For N_runs = 1, interpreter wins (no compile overhead). For N_runs >> 1, compiler crushes it. The N=50 vs N=1000 sum data is exactly this curve playing out: at N=50 raw LLM is 4× cheaper, by N=200 Bricks is 17× cheaper, by N=1000 raw LLM doesn't even complete.

The kicker: **most real-world agent traffic is repeats, not novelty.** Customer support tickets, invoice extraction, log triage, routine analysis — these are the *same problem shape* a million times with different data. Interpreting them every time is just lighting money on fire.

## What the LLM-as-compiler model implies

1. **Brick libraries should be designed like instruction sets, not APIs.** Small, orthogonal, composable. The composer's job gets easier as the catalog gets more "ISA-shaped."
2. **Caching is non-negotiable.** Without the blueprint store, you're a JIT — better than an interpreter, but still re-compiling. Persistent cache is what makes the model actually deterministic.
3. **Validation matters more than generation.** A compiler must reject malformed code; a Bricks validator must reject malformed blueprints. The DSL whitelist + AST validation is the type-checker stage.
4. **The agent becomes hybrid.** Compiled paths handle the known. The LLM only re-engages for genuinely novel queries — exactly like a JIT falling back to the interpreter for cold paths.

## Where it breaks (be honest)

Compiler mode wins for **recurring, structured, deterministic** tasks. It loses for:

- **Genuine novelty.** Open-ended exploration, "summarize my unique situation" — no two queries share a shape, nothing to cache.
- **Judgment-heavy work.** Style, creativity, nuance. You can't compile "be insightful."
- **Tasks that don't decompose into primitives.** If your stdlib doesn't cover the problem, the compiler can't route around the gap.

So: this isn't "LLM-as-interpreter is always wrong." It's **"LLM-as-interpreter is wrong for recurring deterministic work, which happens to be 90% of agent traffic."**

## The thesis sentence for the article

> The LLM-agent industry is treating compilation problems as interpretation problems. Every API call is the LLM "running" the user's intent from source. Bricks shows the alternative: compile the intent once into deterministic, auditable, replayable code. The cost curves, the determinism, the auditability — all fall out of one design choice: **stop asking the LLM to re-derive the answer; ask it to write the program once.**
