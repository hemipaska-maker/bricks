"""Example: loading and running a YAML sequence file.

This example demonstrates:
- Registering @brick-decorated functions
- Loading a sequence from a YAML string
- Executing it with the SequenceEngine
- Reading the output map
"""

from __future__ import annotations

from typing import cast

from bricks.core.brick import BrickFunction, brick
from bricks.core.engine import SequenceEngine
from bricks.core.loader import SequenceLoader
from bricks.core.registry import BrickRegistry
from bricks.core.validation import SequenceValidator

# -- 1. Define bricks ----------------------------------------------------------


@brick(tags=["math"], description="Multiply two numbers together", destructive=False)
def multiply(a: float, b: float) -> float:
    """Multiply a by b."""
    return a * b


@brick(tags=["math"], description="Round a float to N decimal places")
def round_value(value: float, decimals: int = 2) -> float:
    """Round value to the given number of decimal places."""
    return round(value, decimals)


@brick(tags=["io"], description="Format a float as a readable string")
def format_result(value: float, label: str = "Result") -> str:
    """Format a numeric result as a labelled string."""
    return f"{label}: {value}"


# -- 2. Register bricks --------------------------------------------------------

registry = BrickRegistry()
for _fn in (multiply, round_value, format_result):
    _bf = cast(BrickFunction, _fn)
    registry.register(_bf.__brick_meta__.name, _bf, _bf.__brick_meta__)

# -- 3. Define sequence in YAML ------------------------------------------------

SEQUENCE_YAML = """
name: calculate_area
description: "Calculate the area of a rectangle, round it, and format it."
inputs:
  width: "float"
  height: "float"
steps:
  - name: compute_area
    brick: multiply
    params:
      a: ${inputs.width}
      b: ${inputs.height}
    save_as: raw_area

  - name: round_area
    brick: round_value
    params:
      value: ${raw_area}
      decimals: 2
    save_as: rounded_area

  - name: label_result
    brick: format_result
    params:
      value: ${rounded_area}
      label: "Area (m\xb2)"
    save_as: display_string

outputs_map:
  area: "${rounded_area}"
  display: "${display_string}"
"""

# -- 4. Load, validate, and run ------------------------------------------------


def main() -> None:
    """Run the yaml_sequence example."""
    loader = SequenceLoader()
    sequence = loader.load_string(SEQUENCE_YAML)

    validator = SequenceValidator(registry=registry)
    validator.validate(sequence)
    print(f"Sequence '{sequence.name}' validated ({len(sequence.steps)} steps)")

    engine = SequenceEngine(registry=registry)
    outputs = engine.run(sequence, inputs={"width": 7.5, "height": 4.2})

    print("Execution complete")
    print(f"  area    = {outputs['area']}")
    print(f"  display = {outputs['display']}")

    assert outputs["area"] == 31.5  # noqa: S101
    assert outputs["display"] == "Area (m\xb2): 31.5"  # noqa: S101
    print("All assertions passed")


if __name__ == "__main__":
    main()
