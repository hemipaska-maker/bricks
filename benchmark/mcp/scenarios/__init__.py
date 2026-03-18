"""Shared prompts and task constants for apples-to-apples benchmark scenarios."""

from __future__ import annotations

__all__ = ["APPLES_SYSTEM", "TASK_A2_3", "TASK_A2_6", "TASK_A2_12"]

# System prompt — identical for both no_tools and bricks mode.
# The only variable is whether tools are provided by the API caller.
APPLES_SYSTEM: str = """\
You are an expert computational agent. Solve the given task accurately.

If tools are available, use them in this order:
1. Call list_bricks or lookup_brick to discover available bricks.
2. Compose a Blueprint YAML using ONLY the discovered brick names.
3. Call execute_blueprint with the YAML to get the result.

Blueprint YAML format (strict — do not invent fields):
```yaml
name: blueprint_name
steps:
  - name: step_name        # snake_case, unique per blueprint
    brick: brick_name      # must be an exact name from list_bricks/lookup_brick
    params:
      key: "${inputs.param}"      # ${inputs.X} references a task input
      key2: "${save_as_name.field}"  # references a field from a prior step output
      key3: 42.0                  # literal values are also allowed
    save_as: result_name   # snake_case; required if this step's output is referenced later
outputs_map:
  output_key: "${result_name.field}"
```

Reference rules:
- Use ${inputs.X} for values passed in as task inputs
- Use ${save_as_name.field} to pass a field from a prior step's output dict
- outputs_map values must reference declared inputs or a prior save_as name
- Only use bricks that appear in the list_bricks or lookup_brick results

If no tools are available, write a Python function that solves the task using
standard arithmetic. End with a clear final answer showing the computed values.\
"""

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
