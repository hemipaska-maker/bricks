"""Parametric task generator for the complexity-curve benchmark scenario.

Builds an N-step property-valuation math chain programmatically, with
deterministic expected outputs computed in Python.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class GeneratedTask(BaseModel):
    """A programmatically generated benchmark task.

    Attributes:
        task_text: Natural language task description for the LLM.
        expected_outputs: Deterministic expected output values.
        step_count: Number of Blueprint steps in this task.
        required_bricks: Brick names needed to solve this task.
    """

    task_text: str
    expected_outputs: dict[str, Any]
    step_count: int
    required_bricks: list[str] = Field(default_factory=list)


# ── Step recipes ──────────────────────────────────────────────────────────────
# Each recipe is (description_fragment, computation, output_key, brick_name).
# The generator picks the first N recipes and builds the task text + expected
# outputs from them.

# Input constants used across all generated tasks.
_INPUTS: dict[str, float] = {
    "width": 7.5,
    "height": 4.2,
    "price_per_sqm": 3500.0,
    "discount_rate": 0.10,
    "tax_rate": 0.17,
    "monthly_factor": 0.0045,
    "annual_factor": 12.0,
    "maintenance_rate": 0.02,
    "insurance_rate": 0.005,
}


def _compute_chain(steps: int) -> list[dict[str, Any]]:
    """Compute the deterministic step chain for the given step count.

    Each entry has: name, brick, params (as description), result_key, value.

    Args:
        steps: Number of steps to generate.

    Returns:
        List of step dicts with computed values.
    """
    chain: list[dict[str, Any]] = []
    vals: dict[str, float] = {}

    recipes: list[tuple[str, str, str]] = [
        # (step_name, brick, description of what it computes)
        ("area", "multiply", "area = width * height"),
        ("area_rounded", "round_value", "area rounded to 2dp"),
        ("base_price", "multiply", "base_price = area * price_per_sqm"),
        ("base_rounded", "round_value", "base_price rounded to 2dp"),
        ("discount", "multiply", "discount = base_price * discount_rate"),
        ("net_price", "subtract", "net_price = base_price - discount"),
        ("tax", "multiply", "tax = net_price * tax_rate"),
        ("total", "add", "total = net_price + tax"),
        ("total_rounded", "round_value", "total rounded to 2dp"),
        ("monthly", "multiply", "monthly = total * monthly_factor"),
        ("monthly_rounded", "round_value", "monthly rounded to 2dp"),
        ("annual", "multiply", "annual = monthly * annual_factor"),
        ("annual_rounded", "round_value", "annual rounded to 2dp"),
        ("maintenance", "multiply", "maintenance = total * maintenance_rate"),
        ("maint_rounded", "round_value", "maintenance rounded to 2dp"),
        ("insurance", "multiply", "insurance = total * insurance_rate"),
        ("ins_rounded", "round_value", "insurance rounded to 2dp"),
        ("total_cost", "add", "total_cost = total + maintenance + insurance"),
        ("cost_rounded", "round_value", "total_cost rounded to 2dp"),
    ]

    # Reserve last 2 steps for format_result (display strings)
    calc_steps = max(0, steps - 2)
    fmt_steps = min(2, steps)

    for i in range(min(calc_steps, len(recipes))):
        step_name, brick_name, desc = recipes[i]
        value = _evaluate_step(step_name, vals)
        vals[step_name] = value
        chain.append(
            {
                "name": step_name,
                "brick": brick_name,
                "desc": desc,
                "result_key": "result",
                "value": value,
            }
        )

    # Add format_result steps
    if fmt_steps >= 1 and chain:
        last_calc = chain[-1]
        chain.append(
            {
                "name": "total_display",
                "brick": "format_result",
                "desc": f"format '{last_calc['name']}' as display string labelled 'Total'",
                "result_key": "display",
                "value": f"Total: {last_calc['value']}",
            }
        )
    if fmt_steps >= 2 and len(chain) >= 3:
        # Pick a secondary value to format
        secondary = chain[-3]  # two before the first format step
        chain.append(
            {
                "name": "secondary_display",
                "brick": "format_result",
                "desc": f"format '{secondary['name']}' as display string labelled 'Detail'",
                "result_key": "display",
                "value": f"Detail: {secondary['value']}",
            }
        )

    return chain[:steps]


def _evaluate_step(step_name: str, vals: dict[str, float]) -> float:
    """Compute the value for a named step using prior computed values.

    Args:
        step_name: The recipe step name.
        vals: Previously computed values.

    Returns:
        The computed float value.
    """
    i = _INPUTS
    match step_name:
        case "area":
            return i["width"] * i["height"]
        case "area_rounded":
            return round(vals["area"], 2)
        case "base_price":
            return vals["area_rounded"] * i["price_per_sqm"]
        case "base_rounded":
            return round(vals["base_price"], 2)
        case "discount":
            return vals["base_rounded"] * i["discount_rate"]
        case "net_price":
            return vals["base_rounded"] - vals["discount"]
        case "tax":
            return vals["net_price"] * i["tax_rate"]
        case "total":
            return vals["net_price"] + vals["tax"]
        case "total_rounded":
            return round(vals["total"], 2)
        case "monthly":
            return vals["total_rounded"] * i["monthly_factor"]
        case "monthly_rounded":
            return round(vals["monthly"], 2)
        case "annual":
            return vals["monthly_rounded"] * i["annual_factor"]
        case "annual_rounded":
            return round(vals["annual"], 2)
        case "maintenance":
            return vals["total_rounded"] * i["maintenance_rate"]
        case "maint_rounded":
            return round(vals["maintenance"], 2)
        case "insurance":
            return vals["total_rounded"] * i["insurance_rate"]
        case "ins_rounded":
            return round(vals["insurance"], 2)
        case "total_cost":
            return vals["total_rounded"] + vals["maint_rounded"] + vals["ins_rounded"]
        case "cost_rounded":
            return round(vals["total_cost"], 2)
        case _:
            raise ValueError(f"Unknown step: {step_name!r}")


class TaskGenerator:
    """Generates N-step math task descriptions with expected outputs.

    Uses a deterministic recipe based on property valuation calculations.
    """

    def generate(self, steps: int) -> GeneratedTask:
        """Build a property-valuation chain with ``steps`` calculation steps.

        Args:
            steps: Number of Blueprint steps (minimum 3, maximum 19).

        Returns:
            GeneratedTask with task text, expected outputs, and required bricks.

        Raises:
            ValueError: If steps is less than 3.
        """
        if steps < 3:
            raise ValueError(f"Minimum 3 steps required, got {steps}")

        chain = _compute_chain(steps)
        required_bricks = sorted({s["brick"] for s in chain})
        expected_outputs = self._build_expected_outputs(chain)
        task_text = self._build_task_text(chain, steps)

        return GeneratedTask(
            task_text=task_text,
            expected_outputs=expected_outputs,
            step_count=steps,
            required_bricks=required_bricks,
        )

    def _build_expected_outputs(self, chain: list[dict[str, Any]]) -> dict[str, Any]:
        """Build expected outputs dict from the computed chain.

        Args:
            chain: List of computed step dicts.

        Returns:
            Dict of expected output values.
        """
        outputs: dict[str, Any] = {}
        for step in chain:
            if step["brick"] == "format_result":
                outputs[step["name"]] = step["value"]
            else:
                outputs[step["name"]] = step["value"]
        return outputs

    def _build_task_text(self, chain: list[dict[str, Any]], steps: int) -> str:
        """Build the natural language task description.

        Args:
            chain: List of computed step dicts.
            steps: Total step count.

        Returns:
            Task description string.
        """
        # Collect which inputs are referenced
        used_inputs = self._referenced_inputs(chain)
        input_parts = [f"{k}={v}" for k, v in sorted(used_inputs.items())]
        input_str = ", ".join(input_parts)

        step_descs = [s["desc"] for s in chain if s["brick"] != "format_result"]
        steps_str = ", ".join(step_descs)

        fmt_steps = [s for s in chain if s["brick"] == "format_result"]
        fmt_str = ""
        if fmt_steps:
            fmt_parts = [s["desc"] for s in fmt_steps]
            fmt_str = " Also " + " and ".join(fmt_parts) + "."

        # Build return spec
        return_parts: list[str] = []
        for s in chain:
            if s["brick"] == "format_result":
                return_parts.append(f"{s['name']} (str)")
            else:
                return_parts.append(f"{s['name']} (float)")
        # Only return last calc + format steps to keep it manageable
        return_parts = return_parts[-4:]
        return_str = ", ".join(return_parts)

        return (
            f"Calculate property valuation ({steps} steps) for: {input_str}. "
            f"Steps: {steps_str}.{fmt_str} "
            f"Return {return_str}."
        )

    def _referenced_inputs(self, chain: list[dict[str, Any]]) -> dict[str, float]:
        """Determine which input constants are referenced by the chain.

        Args:
            chain: List of computed step dicts.

        Returns:
            Dict of referenced input names to values.
        """
        # Always include width and height
        used: dict[str, float] = {"width": _INPUTS["width"], "height": _INPUTS["height"]}

        input_keywords = {
            "price_per_sqm": "price_per_sqm",
            "discount_rate": "discount_rate",
            "tax_rate": "tax_rate",
            "monthly_factor": "monthly_factor",
            "annual_factor": "annual_factor",
            "maintenance_rate": "maintenance_rate",
            "insurance_rate": "insurance_rate",
        }

        for step in chain:
            desc = step["desc"]
            for keyword, input_name in input_keywords.items():
                if keyword in desc:
                    used[input_name] = _INPUTS[input_name]

        return used
