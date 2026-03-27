# Bricks Benchmark Results

| Scenario | Code Gen | Bricks | Savings |
|---|---|---|---|
| A: Simple Calc | 912 tokens | 921 tokens | 0.99x (-1% less) |
| B: API Pipeline | 1,052 tokens | 1,025 tokens | 1.03x (3% less) |
| C: 10x Session | 5,364 tokens | 922 tokens | 5.82x (83% less) |

## Interpretation

Across all 3 scenarios Bricks used **2,868 tokens** vs **7,328 tokens** for raw code generation — a **2.56x reduction (61% fewer tokens)**. The savings grow with repetition: Scenario C shows that once a Blueprint is generated it can be re-executed with different inputs at near-zero additional token cost, while code generation must regenerate the full function for every new input set.