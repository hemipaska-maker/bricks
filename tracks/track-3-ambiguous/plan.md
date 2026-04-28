# Track 3 — Ambiguous Tasks

**Priority:** P3
**Status:** Blocked on Issue #<TBD> (provider upgrade), plus parking until Tracks 1–2 produce learnings
**Owner:** RA session
**Duration:** ~3 days of experiments + writeup

## Research question

How does Bricks behave when a task is genuinely ambiguous — where "correct" is subjective, multi-valued, or interpretation-dependent? Does Bricks fail gracefully, pick a sensible default, or does the deterministic pipeline make it brittle in ways raw LLMs aren't?

## Why this matters

Bricks' pitch is deterministic execution wins on structured data. Ambiguous tasks are the **anti-case** — where raw LLM reasoning should theoretically shine. This track tests the boundary. If Bricks handles ambiguity gracefully (e.g. by asking for clarification, documenting the interpretation it chose), it's a stronger story. If it fails badly, that's an honest limitation the article should disclose — and a spec for a future "clarify-or-pick" capability.

## Experiment classes

### Class A — Interpretation ambiguity

Task: "Summarize the most interesting customer in this dataset."
- "Interesting" is undefined. Biggest account? Longest tenure? Weirdest behavior?
- Variables: does Bricks compose an interpretation-specific blueprint, or fail to pick?

### Class B — Value judgment

Task: "Recommend which of these 3 vendors to proceed with, given their pitches."
- No objective correct answer. Depends on priorities.
- Variables: does Bricks decline? Invent a framework? Pick arbitrarily?

### Class C — Preference-driven

Task: "Sort these movies from best to worst."
- Subjective. Any order is "correct."
- Variables: how does Bricks handle a non-deterministic target?

### Class D — Under-specified structured task

Task: "Extract the important fields from this contract text."
- "Important" depends on use case.
- Variables: does Bricks hallucinate a schema? Ask for one? Copy everything?

## Variables

- Ambiguity class (A–D above)
- Task complexity (3 levels: trivial, moderate, complex)
- **Kept fixed:** model (sonnet), seed (3 per task), catalog (full stdlib)

## Method

Qualitative-heavy:
1. Author 3 tasks per class × 4 classes = 12 tasks
2. Run each through Bricks and raw-LLM, 3 seeds each = 72 runs
3. For each run, record:
   - Outputs (no expected-output check — there's no "correct" to check against)
   - Blueprint YAML or raw-LLM reasoning trace
   - Behavior tags (e.g. `declined`, `picked-arbitrarily`, `documented-interpretation`, `failed-to-execute`)
4. Human review (by Hemi) of every run → tagging, notes
5. Aggregate by behavior tag × engine × class

## Deliverables

1. `runs/track-3_*.json` — full output + tags
2. `findings.md` — patterns per class
3. `article/track-3-draft.md` — roughly **"Where Bricks struggles, and why that's OK"** section. Honest failure-mode documentation.

## Success criteria

- 12 tasks authored and executed across both engines
- Behavior tags applied consistently
- At least 2 failure modes documented clearly enough to inform roadmap
- Article section serves as the honest "limitations" chapter — builds credibility, doesn't hide weakness

## What could go wrong

- **Ambiguity classes overlap** → merge or split mid-experiment; it's exploratory
- **Human tagging drifts** → establish tag dictionary in `findings.md` before run 1
- **Raw LLM just happens to make the same arbitrary choice Bricks does** → still interesting, document it

## Not a priority until

- Track 1 data is in and the article skeleton exists
- Track 2 has produced at least one concrete finding
- Then Track 3 rounds out the article with honest limitations

## Unblocks (post-track)

- Future capability: "Bricks-with-clarification" — compose stage that asks back before executing on an ambiguous task
- Article's Limitations section — without this track, the article reads as one-sided advocacy

## Blocked by

- Issue #<TBD>: ClaudeCodeProvider JSON output parsing
- Tracks 1 and 2 producing article skeleton first
