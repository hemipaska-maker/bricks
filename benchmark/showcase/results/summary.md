# Bricks Benchmark Results

| Scenario | Code Gen | Bricks | Savings |
|---|---|---|---|
| A: Simple Calc | 367 tokens | 355 tokens | 1.03x (3% less) |
| B: API Pipeline | 611 tokens | 414 tokens | 1.48x (32% less) |
| C: 10x Session | 2,420 tokens | 325 tokens | 7.45x (87% less) |

## Interpretation

Across all 3 scenarios Bricks used **1,094 tokens** vs **3,398 tokens** for raw code generation — a **3.11x reduction (68% fewer tokens)**. The savings grow with repetition: Scenario C shows that once a Blueprint is generated it can be re-executed with different inputs at near-zero additional token cost, while code generation must regenerate the full function for every new input set.