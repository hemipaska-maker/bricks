"""Shared prompts and task generation for apples-to-apples benchmark scenarios."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bricks.core.registry import BrickRegistry

__all__ = ["APPLES_SYSTEM", "build_apples_system"]

# Base system prompt — used for no_tools mode (no brick pool section).
APPLES_SYSTEM: str = """\
You are an expert computational agent. Solve the given task accurately.

If tools are available, you have access to Bricks tools that let you solve \
tasks by composing pre-tested building blocks into a YAML Blueprint, then \
executing it in ONE tool call.

Blueprint YAML format:
```yaml
name: blueprint_name
steps:
  - name: step_name
    brick: brick_name
    params:
      key: "${inputs.param}"
      key2: "${prior_step.field}"
      key3: 42.0
    save_as: result_name
outputs_map:
  output_key: "${result_name.field}"
```

Reference syntax:
- ${inputs.X} — task input passed to execute_blueprint
- ${save_as_name.field} — output field from a prior step
- Literal values (numbers, strings) allowed

Rules:
- Every step referenced later needs save_as.
- outputs_map values must use ${inputs.X} or ${save_as_name.field}.
- Step names must be unique snake_case.

If no tools are available, write a Python function that solves the task using \
standard arithmetic. End with a clear final answer showing the computed values.\
"""

_BRICK_POOL_SECTION: str = """
Available bricks (use ONLY these — do NOT call list_bricks):
```
{brick_signatures}
```

Workflow:
1. Read the task.
2. Compose a Blueprint YAML using ONLY the bricks listed above.
3. Call execute_blueprint with the YAML and inputs.
4. Report the result.

Do NOT call list_bricks or lookup_brick — all bricks are listed above.\
"""


def build_apples_system(registry: BrickRegistry | None = None) -> str:
    """Build the system prompt, optionally injecting compact brick signatures.

    Args:
        registry: If provided, inject brick pool into the prompt so the agent
            skips discovery. If None, return the base prompt (for no-tools mode).

    Returns:
        Complete system prompt string.
    """
    if registry is None:
        return APPLES_SYSTEM

    from bricks.core.schema import compact_brick_signatures

    signatures = compact_brick_signatures(registry)
    return APPLES_SYSTEM + "\n" + _BRICK_POOL_SECTION.format(brick_signatures=signatures)
