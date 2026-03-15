"""Scenario A: Simple calculation — room area, round, format."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from benchmark.showcase.scenarios import CODEGEN_SYSTEM
from benchmark.showcase.tokens import count_tokens

# ── paths ──────────────────────────────────────────────────────────────────
_BLUEPRINTS = Path(__file__).parent.parent / "blueprints"

# Python code-gen must include full function signatures + docstrings so the
# AI knows exact calling conventions -- a fair equivalent to Bricks schemas.
_CODEGEN_USER = """\
Available helper functions (use ONLY these):

def multiply(a: float, b: float) -> dict:
    \"\"\"Multiply two numbers. Returns {'result': float}.\"\"\"

def round_value(value: float, decimals: int = 2) -> dict:
    \"\"\"Round a float to decimal places. Returns {'result': float}.\"\"\"

def format_result(label: str, value: float) -> dict:
    \"\"\"Format label + value as display string. Returns {'display': str}.\"\"\"

Task: Write `calculate_room_area(width: float, height: float) -> dict` that
calls multiply(), round_value(), and format_result() to compute room area,
round to 2dp, and return {'area': float, 'display': str}.
Include type hints, docstring, and error handling for non-positive inputs.
"""

# Simulated AI-generated Python code (what a real LLM would produce)
_GENERATED_CODE = '''\
def calculate_room_area(width: float, height: float) -> dict:
    """Calculate room area, round to 2dp, and return with a display string.

    Args:
        width: Room width in metres. Must be positive.
        height: Room height in metres. Must be positive.

    Returns:
        dict with 'area' (float) and 'display' (str).

    Raises:
        ValueError: If width or height is not positive.
    """
    if width <= 0 or height <= 0:
        raise ValueError(f"Dimensions must be positive, got {width=}, {height=}")
    area = round(width * height, 2)
    display = f"Area (m2): {area}"
    return {"area": area, "display": display}
'''

# ── bricks payload ─────────────────────────────────────────────────────────
_BRICK_SCHEMAS = [
    {
        "name": "multiply",
        "description": "Multiply two numbers and return the result.",
        "parameters": {"a": "float", "b": "float"},
        "returns": {"result": "float"},
    },
    {
        "name": "round_value",
        "description": "Round a float to the specified number of decimal places.",
        "parameters": {"value": "float", "decimals": "int"},
        "returns": {"result": "float"},
    },
    {
        "name": "format_result",
        "description": "Format a labelled numeric result as a display string.",
        "parameters": {"label": "str", "value": "float"},
        "returns": {"display": "str"},
    },
]

_INTENT = "Calculate room area for given width and height, round to 2 decimal places, format as display string."


def code_generation_approach() -> dict[str, Any]:
    """Return token cost and simulated code for the raw code-gen approach."""
    prompt = CODEGEN_SYSTEM + "\n\n" + _CODEGEN_USER
    prompt_tokens = count_tokens(prompt)
    output_tokens = count_tokens(_GENERATED_CODE)
    return {
        "prompt_tokens": prompt_tokens,
        "output_tokens": output_tokens,
        "total_tokens": prompt_tokens + output_tokens,
        "code": _GENERATED_CODE,
    }


def bricks_approach() -> dict[str, Any]:
    """Return token cost and execute the Blueprint for the Bricks approach."""
    schema_payload = json.dumps(_BRICK_SCHEMAS, indent=2)
    blueprint_yaml = (_BLUEPRINTS / "room_area.yaml").read_text()
    prompt = f"Available bricks:\n{schema_payload}\n\nIntent: {_INTENT}"
    prompt_tokens = count_tokens(prompt)
    output_tokens = count_tokens(blueprint_yaml)

    # Actually execute the blueprint to prove it works
    result = _execute_blueprint(blueprint_yaml, {"width": 4.0, "height": 5.5})

    return {
        "prompt_tokens": prompt_tokens,
        "output_tokens": output_tokens,
        "total_tokens": prompt_tokens + output_tokens,
        "blueprint": blueprint_yaml,
        "execution_result": result,
    }


def _execute_blueprint(yaml_str: str, inputs: dict[str, Any]) -> dict[str, Any]:
    """Load and run the blueprint through the Bricks engine."""
    from benchmark.showcase.bricks import build_showcase_registry
    from benchmark.showcase.bricks.math_bricks import multiply, round_value
    from benchmark.showcase.bricks.string_bricks import format_result
    from bricks.core import SequenceEngine, SequenceLoader

    registry = build_showcase_registry(multiply, round_value, format_result)
    loader = SequenceLoader()
    engine = SequenceEngine(registry=registry)
    sequence = loader.load_string(yaml_str)
    return engine.run(sequence, inputs=inputs)
