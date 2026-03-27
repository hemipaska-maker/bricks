# Bricks v0.4.5 -- Apples-to-Apples Benchmark

Same agent · same task · same model · same system prompt.
The only variable: whether Bricks MCP tools are available.

## Scenario A2: Complexity Curve

| Sub-scenario | Steps | No Tools (tokens) | Bricks (tokens) | Bricks turns |
|---|---|---|---|---|
| A2-12 | 12 | 1,089 | 18,019 | 5 |

## Scenario C2: Reuse Economics

10 runs of the 6-step property price task: **0 tokens** (Bricks, first run only) vs **0 tokens** (No Tools, code regenerated every run). After the first run, Bricks reuses the Blueprint at 0 tokens per subsequent run.
