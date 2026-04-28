# Track 2 — Agent Compose

**Priority:** P2
**Status:** Blocked on Issue #<TBD> (ClaudeCodeProvider JSON output upgrade — we want real cost data here too so findings are comparable across tracks)
**Owner:** RA session
**Duration:** open-ended, weekly iterations

## Research questions

1. When an LLM agent receives a structured task, is it cheaper/more reliable to compose with bricks than to generate Python from scratch?
2. What is the ideal **scope** of a brick? (too granular → LLM can't pick; too chunky → no composition room)
3. What is the ideal **prompt format** for LLM-to-blueprint composition?
   - Bullet list of brick names + params?
   - JSON schema of bricks?
   - Few-shot examples?
   - Free-text catalog with descriptions?

These are exploratory, not a grid. Track 2 evolves as findings land.

## Why this matters

Bricks' value prop rests on the assumption that composition beats generation for structured tasks. This track tests that assumption and informs two things:
- Which bricks to keep/merge/split in the stdlib
- How to prompt the compose phase for best results (ships back into `src/bricks/composer/`)

## Starting experiments

### Experiment 2A — Catalog scope

Same task, catalog size varies:
- Full catalog (all ~40 bricks)
- Domain-relevant subset (~10 bricks)
- Minimal subset (~5 bricks)
- 2x expanded (some duplicate/overlapping bricks added)

Measure: compose success rate, blueprint validity, output correctness.
Hypothesis: middle subset wins; too many bricks confuses the LLM, too few makes it improvise.

### Experiment 2B — Prompt format

Same catalog, prompt format varies:
- Plain bullet list with docstrings
- JSON schema per brick
- Few-shot with 2-3 complete blueprints as examples
- Conversational description ("filter a list of dicts by a key-value match using...")

Measure: compose success, blueprint quality, verbosity of output.

### Experiment 2C — Compose vs generate

Give LLM the same task two ways:
- With brick catalog → ask for blueprint YAML
- Without catalog → ask for raw Python code

Run the output, check correctness. Compare success rate, token cost, time-to-first-correct.

## Method

- Build harness in `tracks/track-2-agent-compose/harness.py` — takes (task, catalog, prompt_format), returns (blueprint_or_code, success, tokens, cost)
- Start with 5 tasks drawn from existing `src/bricks/benchmark/` scenarios
- 3 seeds per config for variance
- Qualitative notes as heavy a component as quantitative data

## Deliverables

- `runs/track-2_*.json` — same schema, per-run data
- `findings.md` updated weekly with emerging patterns
- `article/track-2-draft.md` when there's something worth saying

Track 2 output may also produce **recommendations for Coder** (e.g. "split brick X into two", "rewrite compose prompt as format Y"). Those go as GitHub issues via Ops session.

## Success criteria (soft)

- Identified 2+ concrete recommendations for brick catalog refinement
- Identified 1 prompt format clearly superior to baseline
- Article section explains WHY composition beats generation, with examples

## Blocked by

- Issue #<TBD>: ClaudeCodeProvider JSON output parsing. Can technically start with estimated costs but we deferred to keep findings comparable across tracks.

## Parking lot

Questions raised here that deserve their own track later:
- Compose chain-of-thought: does asking the LLM to "think before composing" improve blueprint quality?
- Multi-turn compose: does iterative refinement help?
- Error recovery: what happens when a blueprint fails validation — can the LLM fix it?
