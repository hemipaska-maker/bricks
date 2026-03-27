# Bricks v0.4.2 -- Apples-to-Apples Benchmark

Same agent · same task · same model · same system prompt.
The only variable: whether Bricks MCP tools are available.

## Scenario A2: Complexity Curve

| Sub-scenario | Steps | No Tools (tokens) | Bricks (tokens) | Bricks turns |
|---|---|---|---|---|
| A2-3 | 3 | 1,407 | 7,151 | 4 |
| A2-6 | 6 | 1,638 | 32,036 | 10 |
| A2-12 | 12 | 1,746 | 23,899 | 7 |

## Scenario C2: Reuse Economics

10 runs of the 6-step property price task: **11,988 tokens** (Bricks, first run only) vs **15,151 tokens** (No Tools, code regenerated every run). After the first run, Bricks reuses the Blueprint at 0 tokens per subsequent run.
