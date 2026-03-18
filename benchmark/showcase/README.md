# Bricks Benchmark: Complexity Curve, Reuse Economics & Determinism

> Real numbers from real API calls. No simulations, no estimates.

## The Problem

Every time an AI agent needs to perform a task, it generates Python code from scratch. This means:

- **Full token cost every time** — even for tasks it has done before
- **Different code every time** — variable names change, error handling appears and disappears, docstrings vary
- **No way to validate before running** — you execute generated code and hope it works

Bricks solves this. Instead of generating code, the AI composes a YAML Blueprint that wires together pre-tested Python building blocks. The engine validates and executes it. Same Blueprint, same result. Every time.

## Three Scenarios

### Scenario A: Complexity Curve

The same domain (property valuation) at three step counts. Shows how token costs scale differently:

| Sub-scenario | Steps | Task |
|---|---|---|
| A-3 | 3 steps | Room area: multiply, round, format |
| A-6 | 6 steps | Property price: area + price per sqm + tax + format |
| A-12 | 12 steps | Full valuation: area + price + discount + tax + monthly payment + 2 formats |

**Key insight:** Code generation scales with task complexity (larger prompt + larger output). Bricks scales with schema size — the Blueprint grows, but the schema per brick stays the same.

### Scenario C: Reuse Economics

The A-6 Blueprint (property price) run 10 times with different property inputs.

- **Code generation:** 10 separate API calls, one per input set. Full token cost every time.
- **Bricks:** 1 API call to generate the Blueprint. Runs 2–10 cost zero AI tokens — the Blueprint is stored and executed locally.

This is the core economic argument: **a Blueprint is a reusable artifact.**

### Scenario D: Determinism

The A-6 prompt sent 5 times to the same model. Compare the 5 generated functions.

Then run the A-6 Blueprint 5 times and confirm identical execution every time.

**Key insight:** Code generation produces a different program every time — different variable names, different docstrings, different error handling, different line count. Blueprints are identical on every run. You validate once, trust forever.

## How We Measured

Live Anthropic API calls (Claude claude-haiku-4-5-20251001). Every token count from real `response.usage` — not estimates.

For each scenario:
- **Code gen side:** AI asked to write a Python function using provided helper signatures
- **Bricks side:** AI asked to compose a Blueprint from Brick schemas

## Run It Yourself

```bash
# From the project root
pip install -e ".[ai,benchmark]"
export ANTHROPIC_API_KEY=your-key-here

# All legacy scenarios (estimated mode — no API calls)
python -m benchmark.showcase.run

# All legacy scenarios (live mode — real API calls)
python -m benchmark.showcase.run --live

# Apples-to-apples only (live mode required)
python -m benchmark.showcase.run --live --apples

# Both legacy and apples-to-apples
python -m benchmark.showcase.run --live --all

# Single legacy scenario
python -m benchmark.showcase.run --scenario A
python -m benchmark.showcase.run --scenario C
python -m benchmark.showcase.run --scenario D

# Custom output directory
python -m benchmark.showcase.run --output-dir /tmp/my-results
```

Each run creates a unique timestamped folder inside the output directory:

```
results/
└── run_20260317_143022_v0.1.0/
    ├── results.json           # machine-readable results
    ├── summary.md             # human-readable summary
    ├── determinism_report.md  # Scenario D detailed report
    ├── comparison_chart.png   # bar chart (requires matplotlib)
    ├── benchmark.log          # full execution log
    └── run_metadata.json      # reproducibility metadata
```

## Reproducibility

`run_metadata.json` captures everything needed to reproduce a run:

```json
{
    "bricks_version": "0.1.0",
    "python_version": "3.10.12",
    "timestamp": "2026-03-17T14:30:22",
    "ai_model": "claude-haiku-4-5-20251001",
    "ai_provider": "anthropic",
    "anthropic_sdk_version": "0.45.0",
    "mode": "live",
    "command": "python -m benchmark.showcase.run --live",
    "scenarios_run": ["A-3", "A-6", "A-12", "C", "D"],
    "os": "Windows 10.0",
    "git_commit": "abc1234",
    "git_branch": "development",
    "git_dirty": false
}
```

## Apples-to-Apples Benchmark (v0.4.2+)

The legacy benchmark above uses two separate prompts — one asks the AI to write Python, the other to compose a Blueprint from schemas. That is **not** an apples-to-apples comparison.

Starting with v0.4.2 a true comparison is available: **same agent, same task, same model, same system prompt — the only variable is whether Bricks MCP tools are available.**

### How it works

No actual MCP server is required. Tool responses are served locally using the real Bricks engine:

```
No-tools mode:  Task → Claude (no tools) → writes Python code
Bricks mode:    Task → Claude + {list_bricks, lookup_brick, execute_blueprint}
                     → discovers bricks → composes Blueprint YAML → executes
```

Both modes receive the identical `APPLES_SYSTEM` prompt and the identical task string. Token counts include **all turns** (tool calls, tool results, continuations).

### Apples-to-Apples Scenarios

| Scenario | Description |
|---|---|
| **A2: Complexity Curve** | Same 3 tasks (3/6/12 steps) — no_tools writes code, bricks composes+executes Blueprint |
| **C2: Reuse Economics** | A2-6 task × 10 runs — no_tools regenerates code each time, bricks reuses Blueprint (0 tokens runs 2–10) |
| **D2: Determinism** | A2-6 task × 5 identical runs — compare code variability vs Blueprint consistency |

### Run the apples-to-apples benchmark

```bash
# Apples-to-apples only (live mode required)
python -m benchmark.showcase.run --live --apples

# Both legacy and apples-to-apples
python -m benchmark.showcase.run --live --all
```

Results land in `apples_to_apples/` inside the run folder:

```
run_YYYYMMDD_HHMMSS_vX.Y.Z/
├── apples_to_apples/
│   ├── results.json        # machine-readable comparison
│   ├── summary.md          # human-readable report
│   ├── A2_complexity.json  # per-scenario detail
│   ├── C2_reuse.json
│   └── D2_determinism.json
├── results.json            # legacy benchmark (unchanged)
└── ...
```

## Legacy Benchmark (pre-MCP)

> The scenarios above (A, C, D) use two separate prompts and measure **token payload sizes** for each approach. This is still useful for understanding raw token costs, but it is not a unified agent-level comparison. Use `--apples` for the true apples-to-apples measurement.

## How It Works

```
Today (Code Generation):
  User request → AI generates Python → Run it → Hope it works → Different code next time

With Bricks:
  User request → AI sees Brick schemas (metadata only) → AI composes YAML Blueprint
  → Engine validates (dry-run) → Engine executes tested code → Same result every time
  → Blueprint saved → Reuse forever at zero AI cost
```

The AI never sees source code. It only sees input/output schemas — what each Brick accepts and returns. This keeps the AI's context small and focused. The more you reuse a Blueprint, the larger the token savings.
