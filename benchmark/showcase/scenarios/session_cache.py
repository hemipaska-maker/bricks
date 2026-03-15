"""Scenario C: Repetitive calls — 10 runs showing Bricks reuse advantage."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from benchmark.showcase.tokens import count_tokens

_BLUEPRINTS = Path(__file__).parent.parent / "blueprints"

# 10 different room dimensions to measure across runs
ROOM_INPUTS = [
    {"width": 4.0, "height": 5.5},
    {"width": 3.2, "height": 4.8},
    {"width": 6.0, "height": 3.0},
    {"width": 5.5, "height": 5.5},
    {"width": 2.5, "height": 4.0},
    {"width": 8.0, "height": 3.5},
    {"width": 4.5, "height": 6.0},
    {"width": 7.0, "height": 4.0},
    {"width": 3.0, "height": 3.0},
    {"width": 5.0, "height": 5.0},
]

_CODEGEN_SYSTEM = (
    "You are an expert Python programmer. Generate production-ready Python "
    "code using ONLY the provided helper functions. Do not import anything."
)

# Each code-gen call includes the full function context (fair comparison).
_CODEGEN_USER_TEMPLATE = """\
Available helper functions (use ONLY these):

def multiply(a: float, b: float) -> dict:
    \"\"\"Multiply two numbers. Returns {{'result': float}}.\"\"\"

def round_value(value: float, decimals: int = 2) -> dict:
    \"\"\"Round a float to decimal places. Returns {{'result': float}}.\"\"\"

def format_result(label: str, value: float) -> dict:
    \"\"\"Format label + value as display string. Returns {{'display': str}}.\"\"\"

Task: Write `calculate_room_area(width: float, height: float) -> dict` using
multiply(), round_value(), format_result(). Width={width}, Height={height}.
"""

_BRICK_SCHEMAS = [
    {
        "name": "multiply",
        "description": "Multiply two numbers.",
        "parameters": {"a": "float", "b": "float"},
        "returns": {"result": "float"},
    },
    {
        "name": "round_value",
        "description": "Round a float to decimal places.",
        "parameters": {"value": "float", "decimals": "int"},
        "returns": {"result": "float"},
    },
    {
        "name": "format_result",
        "description": "Format a labelled result as display string.",
        "parameters": {"label": "str", "value": "float"},
        "returns": {"display": "str"},
    },
]

_SIMULATED_PYTHON_OUTPUT = '''\
def calculate_room_area(width: float, height: float) -> dict:
    """Calculate room area."""
    if width <= 0 or height <= 0:
        raise ValueError("Dimensions must be positive")
    area = round(width * height, 2)
    return {"area": area, "display": f"Area (m2): {area}"}
'''


def code_generation_approach() -> dict[str, Any]:
    """Return token cost for 10 separate code-gen calls (one per input set).

    Each call gets a new prompt with different dimensions — the LLM must
    regenerate the full function each time.
    """
    runs = []
    total_tokens = 0

    for i, inp in enumerate(ROOM_INPUTS):
        user_prompt = _CODEGEN_USER_TEMPLATE.format(**inp)
        prompt = _CODEGEN_SYSTEM + "\n\n" + user_prompt
        prompt_tokens = count_tokens(prompt)
        output_tokens = count_tokens(_SIMULATED_PYTHON_OUTPUT)
        run_total = prompt_tokens + output_tokens
        total_tokens += run_total
        runs.append(
            {
                "run": i + 1,
                "inputs": inp,
                "prompt_tokens": prompt_tokens,
                "output_tokens": output_tokens,
                "total_tokens": run_total,
            }
        )

    return {
        "runs": runs,
        "total_tokens": total_tokens,
        "per_run_avg": total_tokens // len(runs),
    }


def bricks_approach() -> dict[str, Any]:
    """Return token cost for 10 runs using one Blueprint.

    Run 1: one LLM call — brick schemas + intent → generates Blueprint YAML.
    Runs 2-10: ZERO LLM tokens — the Blueprint is stored and executed locally
    with different inputs. No re-generation, no API call.
    """
    schema_payload = json.dumps(_BRICK_SCHEMAS, indent=2)
    blueprint_yaml = (_BLUEPRINTS / "room_area.yaml").read_text()

    # Run 1: schema + intent → LLM generates the blueprint (one-time cost)
    intent = "Calculate room area, round, format."
    first_prompt = f"Available bricks:\n{schema_payload}\n\nIntent: {intent}"
    first_prompt_tokens = count_tokens(first_prompt)
    first_output_tokens = count_tokens(blueprint_yaml)
    first_total = first_prompt_tokens + first_output_tokens

    runs = []
    total_tokens = first_total
    runs.append(
        {
            "run": 1,
            "inputs": ROOM_INPUTS[0],
            "prompt_tokens": first_prompt_tokens,
            "output_tokens": first_output_tokens,
            "total_tokens": first_total,
            "note": "LLM call: generate blueprint (one-time)",
        }
    )

    execution_results = []
    engine = _build_engine()
    blueprint_sequence = _load_sequence(blueprint_yaml)

    for i, inp in enumerate(ROOM_INPUTS):
        result = engine.run(blueprint_sequence, inputs=inp)
        execution_results.append({"run": i + 1, "inputs": inp, "output": result})
        if i > 0:
            # No LLM call — 0 additional tokens
            runs.append(
                {
                    "run": i + 1,
                    "inputs": inp,
                    "prompt_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0,
                    "note": "engine execution (no LLM call, 0 tokens)",
                }
            )

    return {
        "runs": runs,
        "total_tokens": total_tokens,
        "per_run_avg": total_tokens // len(runs),
        "execution_results": execution_results,
    }


def _build_engine() -> Any:
    from benchmark.showcase.bricks.math_bricks import multiply, round_value
    from benchmark.showcase.bricks.string_bricks import format_result
    from bricks.core import BrickRegistry, SequenceEngine

    registry = BrickRegistry()
    for fn in (multiply, round_value, format_result):
        registry.register(fn.__name__, fn, fn.__brick_meta__)  # type: ignore[attr-defined]
    return SequenceEngine(registry=registry)


def _load_sequence(yaml_str: str) -> Any:
    from bricks.core import SequenceLoader

    return SequenceLoader().load_string(yaml_str)
