"""Example: Wrapping Bricks as a LangChain tool.

Shows how to expose the Bricks engine as a callable tool for LangChain agents
(or any other framework that expects a plain Python callable).

LangChain is NOT a dependency of Bricks.  The import is shown commented-out
so this file works without installing langchain.

Run (requires ANTHROPIC_API_KEY):
    python examples/langchain_integration.py
"""

from __future__ import annotations

import json
import os

from bricks import Bricks

# ── 1. Boot the engine ───────────────────────────────────────────────────────

# from_skill() makes one LLM call to extract brick categories/tags from the
# markdown description, then the engine is ready.  Subsequent execute() calls
# use the cached blueprint and make zero LLM calls.

engine = Bricks.from_skill(
    "examples/blueprints/skill.md",
    api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
)

# ── 2. Define a plain callable that wraps engine.execute() ──────────────────


def run_bricks_task(task_json: str) -> str:
    """Execute a Bricks task. Input is JSON: {"task": "...", "inputs": {...}}.

    Args:
        task_json: JSON string with ``task`` (str) and optional ``inputs`` (dict).

    Returns:
        JSON string of the execution result.
    """
    payload = json.loads(task_json)
    result = engine.execute(
        task=payload["task"],
        inputs=payload.get("inputs"),
    )
    return json.dumps(result)


# ── 3. Register as a LangChain tool (uncomment when langchain is installed) ──

# from langchain.tools import Tool
#
# bricks_tool = Tool(
#     name="bricks_execute",
#     description=(
#         "Execute a deterministic data processing task using Bricks. "
#         "Input must be a JSON string with 'task' (str) and optional 'inputs' (dict)."
#     ),
#     func=run_bricks_task,
# )

# ── 4. Standalone demo ───────────────────────────────────────────────────────

if __name__ == "__main__":
    import json as _json

    demo_input = _json.dumps(
        {
            "task": "Filter the list for values greater than 10 and return them.",
            "inputs": {"values": [5, 15, 3, 20, 8]},
        }
    )
    print("Input :", demo_input)
    print("Output:", run_bricks_task(demo_input))
