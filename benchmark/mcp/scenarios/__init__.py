"""Shared prompts and task constants for apples-to-apples benchmark scenarios."""

from __future__ import annotations

__all__ = ["APPLES_SYSTEM", "TASK_A2_3", "TASK_A2_6", "TASK_A2_12"]

# System prompt — identical for both no_tools and bricks mode.
# The only variable is whether tools are provided by the API caller.
APPLES_SYSTEM: str = (
    "You are an expert computational agent. Solve the given task accurately and return the result. "
    "If tools are available, use them: call list_bricks to discover available bricks, "
    "lookup_brick to search for specific ones, and execute_blueprint to run a YAML blueprint. "
    "If no tools are available, write a Python function that solves the task using standard arithmetic. "
    "Always provide a clear final answer with the computed values."
)

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
