# Article outline — "The LLM Should Be a Compiler, Not an Interpreter"

**Working title:** *The LLM Should Be a Compiler, Not an Interpreter*
**Format:** Long-form essay, ~2,000–2,500 words
**Audience:** Engineers building LLM agents; technical decision-makers
**Goal:** Make a concrete architectural argument, backed by data, that recurring agent workflows should compile — not interpret — through the LLM.

---

## Section map

### 1. Hook (~200 words)
Open with the **squared-sum scene**: Sonnet faced "sum 50 numbers each squared." It rendered a 50-row markdown table, summed in groups, and got the answer 0.01 wrong while charging $0.46. Bricks ran `sum(v*v for v in values)` — exact, $0.04. The LLM was *trying* to do arithmetic in tokens. That's the moment the framing clicks.

### 2. The thesis (~250 words)
**Most LLM agents are interpreters.** Every request goes through the model. Every word is a fresh decision. Cost is linear in calls; behavior is non-deterministic; latency is variable.

**They should be compilers.** The LLM is good at *semantic translation* (intent → primitives → structure). It's bad at *mechanical execution* (loops, arithmetic, holding 1000 numbers in attention). Use the model where it's strong; cut it out of the loop where it isn't.

The 5-stage table (parse / resolve / optimize / code-gen / cache → Bricks does literally these 5 things). Metaphor as architecture, not rhetoric.

### 3. The cost-curve evidence (~400 words)
Sum-only sweep, two models, sizes 50 → 5000. The full table from findings.md.
- Tipping point at N≈100.
- Raw LLM **doesn't just slow down; it hits a wall** at N=1000 (timeout, not slow answer).
- Bricks stays flat at $0.018/run (Sonnet) and $0.006/run (Haiku) at any size.
- Raw-Haiku fails *earlier* than raw-Sonnet — cheaper model, less reliable.

Side panel: how Anthropic's prompt cache amplifies the win (three-regime breakdown: session-cold, task-cold, task-warm).

### 4. Determinism (~250 words)
10× sum-only N=200 with Sonnet:
- 10/10 byte-identical Bricks outputs (FP noise included)
- 10/10 identical raw-LLM outputs (lucky)
- **2× cost variance on raw LLM** for the same prompt — prompt-cache lottery
- Bricks is bit-identical on **both** axes: answer and cost.

This is what compliance, billing, audit, regression-tested pipelines actually need.

### 5. Where Bricks loses (~300 words)
**Counter-case** (email rewrite): Bricks returned the email *verbatim*. Composer found no "rewrite politely" brick → emitted a no-op pass-through. Cost $0.061. Raw LLM did the task perfectly for $0.022.

**The compiler analogy predicts this exactly.** A compiler can only emit instructions in its target ISA. Style and judgment aren't in the brick catalog and never will be.

**Reliability sweep** (15 task shapes): Bricks 10/15 (66%), raw LLM 14/15 (93%). At small N on one-off tasks, raw LLM is more reliable. The article shouldn't pretend otherwise.

The one raw-LLM failure (squared-sum) is a *Bricks win* — and it's the wedge.

### 6. Failure taxonomy (~250 words)
The 5 Bricks failures from the reliability sweep, named:
- 2× type mismatches at brick I/O boundaries (compose-time check would catch)
- 2× field-pluck missing (composer chose right brick, forgot to extract)
- 1× broken chain producing None-pollution

Each maps to a **known compiler technique**: static type checking, dead-code/canonicalization passes, IR validation. Bricks v0.5 ↔ what a v2.0 LLM-as-compiler looks like.

### 7. What this implies for builders (~350 words)
- **Design brick libraries like ISAs.** Small, orthogonal, composable.
- **Caching is non-negotiable.** Without persistent blueprint store, you're a JIT — better than interpreter, but still re-compiling.
- **Validation matters more than generation.** AST whitelist + type check + grammar pass.
- **Agents become hybrid.** Compiled paths for known. LLM for novel. Like a JIT.
- **Profile-guided optimization is the upside.** Hot blueprints get re-compiled at higher optimization levels automatically. Software that gets *better* with use.
- **AOT mode for production.** Compose offline → ship YAML → no LLM in prod. Compliance-friendly. Reviewable diffs.

### 8. The thesis sentence (~80 words)
> The LLM-agent industry is treating compilation problems as interpretation problems. Every API call is the LLM "running" the user's intent from source. Bricks shows the alternative: compile the intent once into deterministic, auditable, replayable code. The cost curves, the determinism, the auditability — all fall out of one design choice: **stop asking the LLM to re-derive the answer; ask it to write the program once.**

---

## Tone notes

- Not marketing. Not a paper. Tech-blog essay.
- Short sentences. Concrete numbers. Honest counter-cases.
- Lead with evidence; let framing follow.
- One footnote-style sidebar per section ok ("Three regimes," "Cache TTL," etc.) — kept short.
- Code examples sparingly; one or two short snippets, not pages.

## Open questions for review before drafting full

1. Is the title right, or should it lead with the problem (e.g., "Why your LLM agent is melting cash")?
2. Open with the squared-sum scene, or the N=1000 timeout? Both are good hooks.
3. Length target — is 2,000–2,500 words right, or do you want it tighter?
4. Audience: should it lean more toward decision-makers (more "why") or engineers (more "how")?

---

## Draft progress

- [x] Outline
- [ ] §1 Hook
- [ ] §2 Thesis
- [ ] §3 Cost-curve evidence
- [ ] §4 Determinism
- [ ] §5 Where Bricks loses
- [ ] §6 Failure taxonomy
- [ ] §7 What this implies for builders
- [ ] §8 Thesis sentence (closer)
