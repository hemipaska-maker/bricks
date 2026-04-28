# Track 1 — Exploration

**Priority:** P1
**Status:** Blocked on Issue #<TBD> (ClaudeCodeProvider JSON output upgrade), then open-ended
**Owner:** RA session
**Shape:** Field study, not grid experiment
**Duration:** Open-ended. Ships weekly findings; article matures over weeks.

## Mission

Find structured-data use cases where Bricks does interesting things — wins on cost, wins on reliability, loses in surprising ways, exposes a missing brick, or reveals a pattern worth writing up. Each case is a self-contained investigation; the track accumulates them into a case-study library that informs both the article and the brick stdlib.

## Why open-ended

The cost crossover point isn't a single number — it depends heavily on scenario structure (filter-heavy? aggregation-heavy? multi-step? nested data?). A single-scenario grid gives one data point. Five diverse scenarios give a map. Ten give a story.

Also: we don't know in advance what's interesting. Exploration lets surprising findings surface instead of being filtered out by a rigid protocol.

## What a "case" looks like

One case = one use case, fully investigated. A case study file in `cases/<slug>.md` contains:

```
# Case: <slug>

## Domain
One paragraph — what kind of data, where this kind of task shows up in the real world.

## Task specification
What does "done" look like. Input shape, output shape, success criteria.

## Data
Seed data file in `cases/<slug>/data.json` or generator script.

## Hypothesis
What I expect Bricks to do well or badly, and why.

## Experiment
Engines run, grid (if any), seed count.

## Findings
- Cost: Bricks $X vs raw LLM $Y at size N; crossover at M
- Reliability: pass rate per engine
- Tokens: per-run + amortized over reuse
- Qualitative: what went interestingly right or wrong
- Missing bricks: list any gaps identified, with proposals in `proposals/`

## Verdict
Does this case go in the article? Strong / weak / as-limitation / cut.
```

## Seed cases (starting backlog)

Not a prescription — pick the most interesting, add your own:

1. **`crm-pipeline`** — existing benchmark scenario. Baseline. (Already largely characterized.)
2. **`log-analysis`** — parse unstructured-ish logs, count errors by severity, identify top error patterns. Tests string manipulation + aggregation brick combos.
3. **`invoice-extraction`** — pull line items + totals from invoice JSON/XML. Tests nested parsing + arithmetic validation.
4. **`contract-clause-search`** — given contract text, find clauses matching criteria. Tests text search + structured output.
5. **`scientific-data-munging`** — CSV with heterogeneous rows, clean + validate + pivot. Tests type coercion + reshape bricks.
6. **`social-feed-aggregation`** — normalize posts from N sources into one schema, compute engagement metrics. Tests schema mapping + time-window aggregation.
7. **`financial-reconciliation`** — match transactions across two sources, flag mismatches. Tests join + diff bricks.
8. **`survey-response-coding`** — coerce free-text survey answers into categorical buckets. Tests classification-like brick composition.

Pick the first case based on what's interesting, not list order.

## Per-case workflow

1. **Pick** a case (from seed list, or propose a new one and log it in `cases/_backlog.md`)
2. **Scope** — write `cases/<slug>.md` through the `Hypothesis` section before running anything
3. **Build data** — minimal seed, 3–5 sizes (small → big) to probe scale behavior
4. **Run** both engines. Start with sonnet; add haiku/opus only if case warrants
5. **Analyze** — fill in `Findings` and `Verdict`
6. **Propose bricks** if gaps surfaced → `proposals/brick-<name>.md`, flag to Hemi
7. **Move on** — don't exhaust one case; diverse signal > deep signal

Each case: ~half a day to a day. Ship findings weekly.

## Measurements per case

From upgraded `ClaudeCodeProvider` (post-Issue #<TBD>):
- Real tokens, cost, duration per run
- Cache creation vs read split
- Blueprint YAML for Bricks runs
- Raw-LLM reasoning trace when available

## Brick proposal format

When a case reveals a missing brick, write `proposals/brick-<name>.md`:

```
# Brick proposal: <name>

## Category
string | list | dict | numeric | date | io | ...

## Signature
brick(input, params) → output — one line

## Motivation
Which case(s) needed this. Quote the blueprint YAML that would use it.

## Spec
- Input types, param schema, output type
- Edge cases

## Example
Tiny YAML snippet showing use in context.

## Test cases
3–5 input/output pairs.
```

Then flag to Hemi → Ops opens GitHub Issue → Coder implements. RA does NOT write brick code directly.

## Deliverables

- `cases/` — ongoing case study library
- `proposals/` — brick proposals awaiting Coder
- `findings.md` — cross-case patterns, updated weekly
- `article/track-1-draft.md` — builds case by case; cost-curve chart becomes a composite across cases

## Success (soft — this is exploratory)

- 3+ cases fully written up in the first week post-unblock
- 1+ brick proposal that ships as a real PR
- Cost-curve insights that hold across multiple cases, not one
- At least one surprising finding worth a callout in the article

## What could go wrong

- **Rabbit-holing** — one fascinating case eats two weeks. Mitigate: half-day-to-a-day per case; park deep threads in `notes/ideas.md` as sub-investigations
- **Generalization failure** — results don't hold across cases, no coherent story emerges. That's a finding too; write it up
- **Case proliferation with no article progress** — pause at case 5 and write the article skeleton before running case 6

## Blocked by

- Issue #<TBD>: ClaudeCodeProvider JSON output parsing. Exploration starts once real cost data is available.

## Parking lot

Case ideas that surface but aren't the next one — append here as they come up.
