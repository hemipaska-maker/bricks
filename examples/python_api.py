"""Example: Python API usage with Bricks.

Demonstrates booting from a YAML config and executing a task.

Run (requires ANTHROPIC_API_KEY and a valid agent.yaml):
    python examples/python_api.py
"""

from __future__ import annotations

import os

from bricks import Bricks

# Boot from a YAML config — no LLM call at this stage.
# The config file declares brick categories so the selector can narrow the search.
#
# Example agent.yaml:
#
#   name: data_processor
#   description: "Processes lists of numbers."
#   brick_categories:
#     - math_numeric
#     - list_operations
#   model: claude-haiku-4-5-20251001
#
engine = Bricks.from_config(
    "examples/blueprints/agent.yaml",
    api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
)

# Execute a natural-language task.
# The engine composes a YAML blueprint on first call, then caches it for re-use.
result = engine.execute(
    task="Sum the list of values and return the total.",
    inputs={"values": [10.0, 20.0, 30.0]},
)

print("Outputs   :", result["outputs"])
print("Cache hit :", result["cache_hit"])
print("API calls :", result["api_calls"])
print("Tokens    :", result["tokens_used"])
