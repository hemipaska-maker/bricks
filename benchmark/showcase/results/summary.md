# Bricks Benchmark Results

| Scenario | Code Gen | Bricks | Savings |
|---|---|---|---|
| A: Simple Calc | 739 tokens | 921 tokens | 0.8x (-25% less) |
| B: API Pipeline | 1,069 tokens | 1,024 tokens | 1.04x (4% less) |
| C: 10x Session | 5,186 tokens | 921 tokens | 5.63x (82% less) |

## Interpretation

Across all 3 scenarios Bricks used **2,866 tokens** vs **6,994 tokens** for raw code generation — a **2.44x reduction (59% fewer tokens)**. The savings grow with repetition: Scenario C shows that once a Blueprint is generated it can be re-executed with different inputs at near-zero additional token cost, while code generation must regenerate the full function for every new input set.