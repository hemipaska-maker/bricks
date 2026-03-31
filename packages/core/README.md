# bricks-ai

**LLMs guess. Bricks computes.**

Bricks is a deterministic execution engine for AI agents. Your LLM writes a YAML blueprint from pre-tested building blocks. Bricks validates it, then executes it — same input, same output, every time.

## Install

```bash
pip install bricks-ai
pip install "bricks-ai[stdlib,ai]"   # with standard library and LLM support
```

## Quick Start

```python
from bricks.api import Bricks

engine = Bricks.default()
result = engine.execute(
    "filter active customers and count them",
    {"data": customers_list}
)
print(result["outputs"])   # {"active_customers": [...], "count": 42}
print(result["cache_hit"]) # True on second call — zero tokens!
```

## Full Documentation

See the [main repository README](https://github.com/hemipaska-maker/bricks#readme) for full documentation, benchmarks, and examples.
