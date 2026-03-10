"""Example: AI-powered sequence composition with SequenceComposer.

This example demonstrates two modes:

  Demo mode  (default, no API key needed):
    Uses a pre-written YAML response to show the full compose→validate→run
    pipeline without making a real API call.

  Live mode  (requires anthropic package + API key):
    Calls the Anthropic Messages API and asks Claude to generate a sequence
    from a natural language intent string.

Usage::

    # Demo mode (no key required)
    python examples/ai_composer.py

    # Live mode
    ANTHROPIC_API_KEY=sk-ant-... python examples/ai_composer.py --live

    # Or pass the key explicitly
    python examples/ai_composer.py --live --api-key sk-ant-...
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any

from bricks.core.brick import brick
from bricks.core.engine import SequenceEngine
from bricks.core.registry import BrickRegistry
from bricks.core.schema import registry_schema
from bricks.core.validation import SequenceValidator

# ── 1. Define a small library of bricks ──────────────────────────────────────


@brick(tags=["math"], description="Add two numbers together")
def add(a: float, b: float) -> float:
    """Return a + b."""
    return a + b


@brick(tags=["math"], description="Multiply two numbers together")
def multiply(a: float, b: float) -> float:
    """Return a * b."""
    return a * b


@brick(tags=["math"], description="Round a float to a given number of decimal places")
def round_value(value: float, decimals: int = 2) -> float:
    """Return value rounded to decimals places."""
    return round(value, decimals)


@brick(tags=["math"], description="Subtract b from a")
def subtract(a: float, b: float) -> float:
    """Return a - b."""
    return a - b


@brick(tags=["io"], description="Format a float as a labelled string, e.g. 'Score: 87.5'")  # noqa: E501
def format_label(value: float, label: str) -> str:
    """Return '{label}: {value}'."""
    return f"{label}: {value}"


# ── 2. Register bricks ────────────────────────────────────────────────────────


def build_registry() -> BrickRegistry:
    """Create a registry populated with the example bricks."""
    registry = BrickRegistry()
    for fn in (add, multiply, subtract, round_value, format_label):
        registry.register(fn.__name__, fn, fn.__brick_meta__)  # type: ignore[attr-defined]
    return registry


# ── 3. Demo mode: simulate a composed sequence without an API call ─────────────


# This is what a well-behaved Claude response would look like for the intent:
# "Calculate the total price of N items at a unit price, apply a discount
#  percentage, round to 2 decimal places, and return a formatted label."
_DEMO_INTENT = (
    "Calculate the total price of N items at a given unit price, "
    "subtract a discount (given as a decimal fraction, e.g. 0.10 for 10%), "
    "round to 2 decimal places, and return a formatted label."
)

_DEMO_YAML = """
name: discounted_price
description: "Total price minus a fractional discount, rounded and labelled."
inputs:
  quantity: "float"
  unit_price: "float"
  discount_fraction: "float"
steps:
  - name: gross_total
    brick: multiply
    params:
      a: "${inputs.quantity}"
      b: "${inputs.unit_price}"
    save_as: gross

  - name: compute_savings
    brick: multiply
    params:
      a: "${gross}"
      b: "${inputs.discount_fraction}"
    save_as: savings

  - name: net_total
    brick: subtract
    params:
      a: "${gross}"
      b: "${savings}"
    save_as: net

  - name: rounded_net
    brick: round_value
    params:
      value: "${net}"
      decimals: 2
    save_as: price

  - name: labelled_price
    brick: format_label
    params:
      value: "${price}"
      label: "Final price"
    save_as: display

outputs_map:
  gross: "${gross}"
  savings: "${savings}"
  price: "${price}"
  display: "${display}"
"""


def run_demo(registry: BrickRegistry) -> None:
    """Run the example in demo mode using a pre-written YAML sequence."""
    print("=" * 60)
    print("DEMO MODE  (no API key required)")
    print("=" * 60)
    print(f"\nIntent:\n  {_DEMO_INTENT}\n")

    # Show which bricks are available
    schemas = registry_schema(registry)
    print(f"Available bricks ({len(schemas)}):")
    for s in schemas:
        tags = f" [{', '.join(s['tags'])}]" if s["tags"] else ""
        print(f"  {s['name']}{tags} - {s['description']}")

    # Parse the pre-written YAML (same path the real composer would take)
    from bricks.core.loader import SequenceLoader

    loader = SequenceLoader()
    sequence = loader.load_string(_DEMO_YAML)

    print(f"\nComposed sequence: {sequence.name!r}")
    print(f"  Description: {sequence.description}")
    print(f"  Inputs:  {list(sequence.inputs.keys())}")
    print(f"  Steps:   {len(sequence.steps)}")
    for step in sequence.steps:
        print(f"    [{step.name}]  brick={step.brick}  save_as={step.save_as}")
    print(f"  Outputs: {list(sequence.outputs_map.keys())}")

    # Validate
    validator = SequenceValidator(registry=registry)
    errors = validator.validate(sequence)
    assert errors == [], f"Validation failed: {errors}"
    print("\nOK Sequence validated (no errors)")

    # Execute with sample inputs: 5 items x 12.00 each, 10% discount (0.10)
    # Expected: gross=60, savings=6, net=54, price=54.0
    inputs = {"quantity": 5.0, "unit_price": 12.0, "discount_fraction": 0.10}
    print(f"\nRunning with inputs: {inputs}")
    engine = SequenceEngine(registry=registry)
    outputs = engine.run(sequence, inputs=inputs)

    print("\nOutputs:")
    for k, v in outputs.items():
        print(f"  {k}: {v!r}")

    assert outputs["gross"] == 60.0,   f"Expected gross=60.0, got {outputs['gross']}"
    assert outputs["savings"] == 6.0,  f"Expected savings=6.0, got {outputs['savings']}"
    assert outputs["price"] == 54.0,   f"Expected price=54.0, got {outputs['price']}"
    assert outputs["display"] == "Final price: 54.0"

    print("\nOK Demo complete. All outputs verified.")


# ── 4. Live mode: real API call ───────────────────────────────────────────────


def run_live(registry: BrickRegistry, api_key: str) -> None:
    """Run the example in live mode — calls the Anthropic API."""
    print("=" * 60)
    print("LIVE MODE  (real API call)")
    print("=" * 60)

    try:
        from bricks.ai.composer import ComposerError, SequenceComposer
    except ImportError:
        print(
            "\nError: the 'anthropic' package is not installed.\n"
            "Install it with:  pip install bricks[ai]\n",
            file=sys.stderr,
        )
        sys.exit(1)

    intent = (
        "Given a quantity and unit price, compute the gross total, "
        "then apply a discount percentage to get the net price, "
        "round it to 2 decimal places, and return the result."
    )

    print(f"\nIntent:\n  {intent}\n")
    print(f"Model: {SequenceComposer.DEFAULT_MODEL}")
    print("Calling Anthropic API …\n")

    composer = SequenceComposer(registry=registry, api_key=api_key)

    try:
        sequence = composer.compose(intent)
    except ComposerError as exc:
        print(f"Composition failed: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Composed sequence: {sequence.name!r}")
    print(f"  Steps ({len(sequence.steps)}):")
    for step in sequence.steps:
        print(f"    [{step.name}]  brick={step.brick}  save_as={step.save_as}")
    print(f"  Outputs: {list(sequence.outputs_map.keys())}")

    # Validate against the registry
    validator = SequenceValidator(registry=registry)
    try:
        validator.validate(sequence)
        print("\nOK Sequence validated")
    except Exception as exc:
        print(f"\nValidation errors: {exc}", file=sys.stderr)
        print("(The AI-generated sequence has structural issues — try again.)")
        sys.exit(1)

    # Run with sample inputs: 5 items x 12.00 each, 10% discount as a fraction
    inputs: dict[str, Any] = {"quantity": 5.0, "unit_price": 12.0, "discount_fraction": 0.10}
    print(f"\nRunning with inputs: {inputs}")

    engine = SequenceEngine(registry=registry)
    try:
        outputs = engine.run(sequence, inputs=inputs)
    except Exception as exc:
        print(f"\nExecution error: {exc}", file=sys.stderr)
        sys.exit(1)

    print("\nOutputs:")
    for k, v in outputs.items():
        print(f"  {k}: {v!r}")

    print("\nOK Live composition and execution complete.")


# ── 5. Entry point ────────────────────────────────────────────────────────────


def main() -> None:
    """Parse arguments and run the selected mode."""
    parser = argparse.ArgumentParser(
        description="Bricks AI composer example",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Call the real Anthropic API (requires anthropic package + key).",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("ANTHROPIC_API_KEY", ""),
        help="Anthropic API key (defaults to $ANTHROPIC_API_KEY).",
    )
    args = parser.parse_args()

    registry = build_registry()

    if args.live:
        if not args.api_key:
            print(
                "Error: --live mode requires an API key.\n"
                "Set $ANTHROPIC_API_KEY or pass --api-key sk-ant-...",
                file=sys.stderr,
            )
            sys.exit(1)
        run_live(registry, api_key=args.api_key)
    else:
        run_demo(registry)


if __name__ == "__main__":
    main()
