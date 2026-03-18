"""Shared prompts and task constants for apples-to-apples benchmark scenarios."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bricks.core.registry import BrickRegistry

__all__ = ["APPLES_SYSTEM", "TASK_A2_3", "TASK_A2_6", "TASK_A2_12", "build_apples_system"]

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


# ── Shared task strings ───────────────────────────────────────────────────────
# SAME prompt used in both no_tools and bricks mode. The only difference is
# which tools (if any) are attached to the API call.

TASK_A2_3: str = (
    "Calculate the room area for width=7.5 metres and height=4.2 metres. "
    "Round the result to 2 decimal places and produce a formatted display string "
    "labelled 'Area (m2)'. Return the area (float) and display (str)."
)

TASK_A2_6: str = (
    "Calculate the property price for: width=7.5, height=4.2 (metres), "
    "price_per_sqm=3500.0 (EUR), tax_rate=0.17. "
    "Steps: area = width * height (rounded to 2dp), "
    "base_price = area * price_per_sqm, tax = base_price * tax_rate, "
    "total = base_price + tax. "
    "Return the total (float) and a formatted display string labelled 'Total (EUR)'."
)

TASK_A2_12: str = (
    "Calculate full property valuation for: width=7.5, height=4.2 (metres), "
    "price_per_sqm=3500.0 (EUR), discount_rate=0.10, tax_rate=0.17, monthly_factor=0.0045. "
    "Steps: area = width * height (rounded to 2dp), base_price = area * price_per_sqm, "
    "discount_amount = base_price * discount_rate, net_price = base_price - discount_amount, "
    "tax = net_price * tax_rate, total = net_price + tax (rounded to 2dp), "
    "monthly = total * monthly_factor (rounded to 2dp). "
    "Return total (float), monthly (float), total_display (str, labelled 'Total'), "
    "monthly_display (str, labelled 'Monthly')."
)
