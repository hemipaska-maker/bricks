# Bricks Benchmark: Token Savings & Determinism

> Real numbers from real API calls. No simulations, no estimates.

## The Problem

Every time an AI agent needs to perform a task, it generates Python code from scratch. This means:

- **Full token cost every time** — even for tasks it has done before
- **Different code every time** — variable names change, error handling appears and disappears, docstrings vary
- **No way to validate before running** — you execute generated code and hope it works

Bricks solves this. Instead of generating code, the AI composes a YAML Blueprint that wires together pre-tested Python building blocks. The engine validates and executes it. Same Blueprint, same result. Every time.

## How We Measured

We ran three token-usage scenarios and one determinism scenario using **live Anthropic API calls** (Claude claude-sonnet-4-20250514). Every number below comes from actual `response.usage` token counts — not estimates.

For each scenario, the AI was given the same task twice: once asked to generate Python code, once asked to compose a Blueprint from Brick schemas. We compared the total tokens consumed.

## Results: Token Usage

| Scenario | Code Generation | Bricks | Ratio | Savings |
|---|---|---|---|---|
| A: Simple Calc (single call) | 671 tokens | 921 tokens | 0.73x | **-37%** (Bricks costs more) |
| B: API Pipeline (single call) | 1,039 tokens | 1,025 tokens | 1.01x | **1%** (roughly even) |
| C: Reusable Artifact (10 runs) | 5,518 tokens | 922 tokens | 5.98x | **83% fewer tokens** |
| **Total** | **7,228 tokens** | **2,868 tokens** | **2.52x** | **60% fewer tokens** |

### Reading the Results Honestly

**Bricks does not save tokens on a single call.** Scenario A shows this clearly — for a simple calculation, generating Python code (671 tokens) is actually cheaper than sending Brick schemas + composing a Blueprint (921 tokens). Scenario B is roughly a wash.

**Bricks saves tokens through reuse.** Scenario C is where the economics flip. The same "calculate room area" task was run 10 times with different inputs:

- Code generation paid full price 10 times: **5,518 tokens** (10 separate API calls, each generating the full function)
- Bricks paid once for the Blueprint, then reused it 9 more times at zero AI cost: **922 tokens** (1 API call + 9 local executions)

This is the core economic argument: **a Blueprint is a reusable artifact.** Once composed, it runs forever without AI involvement. Code generation pays full price every time.

### When This Matters in the Real World

The 10-run scenario isn't artificial. These are everyday patterns where the same operation runs repeatedly:

- **CI/CD pipelines** running the same test sequence on every commit
- **Data processing** applying the same transformation to hundreds of files
- **Scheduled automation** running hourly or daily tasks
- **Hardware test sequences** running identical checks on multiple devices
- **Multi-tenant SaaS** where every user triggers the same workflow

In these scenarios, code generation costs scale linearly with usage. Bricks costs are nearly flat.

## Results: Determinism

We asked Claude to generate the **exact same function** 5 times with the **identical prompt**. Then we compared the outputs.

| Metric | Code Generation (5 runs) | Bricks Blueprint (5 runs) |
|---|---|---|
| Unique variable names | **18** distinct names across runs | N/A — no variables, just YAML wiring |
| Function signatures identical | 1 (same signature, different internals) | Blueprint schema is fixed |
| Error handling consistent | Present in all 5, but **implemented differently** each time | Built into the Brick — always the same |
| Docstring length | Varied: 594 to 738 characters | Fixed description in Brick metadata |
| Lines of code | Ranged from 34 to 38 | Blueprint is always 27 lines |
| Exact duplicates | **0 out of 5** — every generation was unique | All 5 executions identical |
| Pre-execution validation | None — run it and hope | Dry-run validation before every execution |

### What 18 Variable Names Means

Across 5 generations of the same function, the AI used 18 distinct variable names. Here is a sample — same prompt, same model, same task:

- Generation 1: `width_float`, `height_float`, `area_value`, `format_result_dict`
- Generation 2: `multiplication_result`, `area_value`, `format_result_output`
- Generation 3: `area_value`, `format_result_data`
- Generation 4: `raw_area`, `area`, `format_result_output`
- Generation 5: `area_raw`, `area_rounded`, `format_result_dict`, `multiply_result`

The logic is similar. The code is never the same. If you are building systems that depend on consistent, predictable behavior — testing, auditing, compliance — this matters.

### The Blueprint Alternative

This is the Blueprint that ran all 5 times. It never changed.

```yaml
name: room_area
description: "Calculate room area, round it, and format a display string"
inputs:
  width: "float"
  height: "float"
steps:
  - name: calculate_area
    brick: multiply
    params:
      a: "${inputs.width}"
      b: "${inputs.height}"
    save_as: area
  - name: round_area
    brick: round_value
    params:
      value: "${area.result}"
      decimals: 2
    save_as: rounded
  - name: format_display
    brick: format_result
    params:
      label: "Area (m2)"
      value: "${rounded.result}"
    save_as: formatted
outputs_map:
  area: "${rounded.result}"
  display: "${formatted.display}"
```

No variables to rename. No docstrings to vary. No error handling to forget. The AI's only job is picking the right Bricks and wiring their outputs to inputs. The engine does the rest — the same way, every time.

### Hallucination Detection

In this benchmark run, **0 out of 5** code generations contained hallucinations (wrong function names, missing steps, syntax errors, or incorrect return types). This rate varies across runs — which itself proves the non-determinism. With Blueprints, hallucination risk is structurally eliminated: the engine validates every step against the Brick's schema before execution begins.

## How It Works

```
Today (Code Generation):
  User request → AI generates Python → Run it → Hope it works → Different code next time

With Bricks:
  User request → AI sees Brick schemas (metadata only) → AI composes YAML Blueprint
  → Engine validates (dry-run) → Engine executes tested code → Same result every time
  → Blueprint saved → Reuse forever at zero AI cost
```

The AI never sees source code. It only sees input/output schemas — what each Brick accepts and returns. This keeps the AI's context small and focused, which is why Bricks wins on repeated usage even though the initial schema payload is larger than a single code generation.

## Run It Yourself

```bash
# From the project root
cd benchmark/showcase

# Install dependencies
pip install tiktoken matplotlib anthropic

# Run with real API calls (requires ANTHROPIC_API_KEY)
export ANTHROPIC_API_KEY=your-key-here
python run_benchmark.py --real

# Run specific scenarios
python run_benchmark.py --real --scenario A
python run_benchmark.py --real --scenario D

# Results are written to results/
ls results/
# results.json  summary.md  determinism_report.md
```

## Benchmark Details

**Model:** Claude claude-sonnet-4-20250514 via Anthropic API
**Token counting:** Real `response.usage.input_tokens` + `response.usage.output_tokens` from API responses
**Date:** March 15, 2026
**Scenarios:**

- **A (Simple Calc):** Calculate room area → multiply, round, format. Single call.
- **B (API Pipeline):** Fetch API data → extract field → format. Single call.
- **C (Reusable Artifact):** Same as A, but run 10 times with different inputs. Code gen pays 10x. Bricks pays 1x.
- **D (Determinism):** Generate the same function 5 times. Compare variable names, structure, error handling. Then run the Blueprint 5 times and confirm identical execution.

## What This Proves

1. **Bricks is not cheaper for one-off tasks.** If you need a function once, code generation is fine.
2. **Bricks is dramatically cheaper for repeated tasks.** The more you reuse a Blueprint, the more tokens you save.
3. **Bricks is deterministic.** Code generation produces different code every time. Blueprints produce identical execution every time. You validate once, trust forever.
