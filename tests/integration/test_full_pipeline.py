"""Integration tests: full pipeline from YAML to executed results."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from bricks.core.brick import brick
from bricks.core.engine import SequenceEngine
from bricks.core.exceptions import BrickExecutionError, SequenceValidationError
from bricks.core.loader import SequenceLoader
from bricks.core.registry import BrickRegistry
from bricks.core.validation import SequenceValidator


def _make_math_registry() -> BrickRegistry:
    reg = BrickRegistry()

    @brick(tags=["math"], description="Add two numbers")
    def add(a: float, b: float) -> float:
        return a + b

    @brick(tags=["math"], description="Multiply two numbers")
    def multiply(a: float, b: float) -> float:
        return a * b

    @brick(tags=["math"], description="Round a float")
    def round_val(value: float, decimals: int = 2) -> float:
        return round(value, decimals)

    @brick(tags=["io"])
    def to_string(value: float) -> str:
        return str(value)

    reg.register("add", add, add.__brick_meta__)  # type: ignore[attr-defined]
    reg.register("multiply", multiply, multiply.__brick_meta__)  # type: ignore[attr-defined]
    reg.register("round_val", round_val, round_val.__brick_meta__)  # type: ignore[attr-defined]
    reg.register("to_string", to_string, to_string.__brick_meta__)  # type: ignore[attr-defined]
    return reg


class TestSingleStepPipeline:
    def test_single_step_add(self) -> None:
        reg = _make_math_registry()
        loader = SequenceLoader()
        seq = loader.load_string("""
name: simple_add
inputs:
  x: "float"
  y: "float"
steps:
  - name: add_step
    brick: add
    params:
      a: "${inputs.x}"
      b: "${inputs.y}"
    save_as: total
outputs_map:
  result: "${total}"
""")
        engine = SequenceEngine(registry=reg)
        out = engine.run(seq, inputs={"x": 3.0, "y": 4.0})
        assert out["result"] == 7.0

    def test_literal_params(self) -> None:
        reg = _make_math_registry()
        loader = SequenceLoader()
        seq = loader.load_string("""
name: literal_add
steps:
  - name: step
    brick: add
    params:
      a: 10.0
      b: 5.0
    save_as: total
outputs_map:
  result: "${total}"
""")
        engine = SequenceEngine(registry=reg)
        out = engine.run(seq)
        assert out["result"] == 15.0

    def test_string_output(self) -> None:
        reg = _make_math_registry()
        loader = SequenceLoader()
        seq = loader.load_string("""
name: to_str
steps:
  - name: s1
    brick: to_string
    params:
      value: 42.0
    save_as: text
outputs_map:
  label: "${text}"
""")
        engine = SequenceEngine(registry=reg)
        out = engine.run(seq)
        assert out["label"] == "42.0"

    def test_no_outputs_map(self) -> None:
        reg = _make_math_registry()
        loader = SequenceLoader()
        seq = loader.load_string("""
name: no_outputs
steps:
  - name: step
    brick: add
    params:
      a: 1.0
      b: 2.0
""")
        engine = SequenceEngine(registry=reg)
        out = engine.run(seq)
        assert out == {}


class TestMultiStepPipeline:
    def test_chained_steps(self) -> None:
        reg = _make_math_registry()
        loader = SequenceLoader()
        seq = loader.load_string("""
name: chain
inputs:
  a: "float"
  b: "float"
  c: "float"
steps:
  - name: first_add
    brick: add
    params:
      a: "${inputs.a}"
      b: "${inputs.b}"
    save_as: ab_sum
  - name: second_add
    brick: add
    params:
      a: "${ab_sum}"
      b: "${inputs.c}"
    save_as: final_sum
outputs_map:
  total: "${final_sum}"
""")
        engine = SequenceEngine(registry=reg)
        out = engine.run(seq, inputs={"a": 1.0, "b": 2.0, "c": 3.0})
        assert out["total"] == 6.0

    def test_multiply_then_round(self) -> None:
        reg = _make_math_registry()
        loader = SequenceLoader()
        seq = loader.load_string("""
name: mul_round
inputs:
  x: "float"
  y: "float"
steps:
  - name: mul
    brick: multiply
    params:
      a: "${inputs.x}"
      b: "${inputs.y}"
    save_as: product
  - name: rnd
    brick: round_val
    params:
      value: "${product}"
      decimals: 2
    save_as: rounded
outputs_map:
  result: "${rounded}"
""")
        engine = SequenceEngine(registry=reg)
        out = engine.run(seq, inputs={"x": 7.5, "y": 4.2})
        assert out["result"] == 31.5

    def test_three_steps_chained(self) -> None:
        reg = _make_math_registry()
        loader = SequenceLoader()
        seq = loader.load_string("""
name: triple_chain
steps:
  - name: s1
    brick: add
    params:
      a: 2.0
      b: 3.0
    save_as: r1
  - name: s2
    brick: multiply
    params:
      a: "${r1}"
      b: 4.0
    save_as: r2
  - name: s3
    brick: round_val
    params:
      value: "${r2}"
      decimals: 1
    save_as: r3
outputs_map:
  result: "${r3}"
""")
        engine = SequenceEngine(registry=reg)
        out = engine.run(seq)
        assert out["result"] == 20.0  # (2+3)*4 = 20

    def test_add_then_stringify(self) -> None:
        reg = _make_math_registry()
        loader = SequenceLoader()
        seq = loader.load_string("""
name: add_then_str
steps:
  - name: sum_step
    brick: add
    params:
      a: 8.0
      b: 2.0
    save_as: sum_result
  - name: str_step
    brick: to_string
    params:
      value: "${sum_result}"
    save_as: text_result
outputs_map:
  label: "${text_result}"
""")
        engine = SequenceEngine(registry=reg)
        out = engine.run(seq)
        assert out["label"] == "10.0"


class TestValidationIntegration:
    def test_validate_then_run(self) -> None:
        reg = _make_math_registry()
        loader = SequenceLoader()
        seq = loader.load_string("""
name: validated_seq
inputs:
  n: "float"
steps:
  - name: double
    brick: multiply
    params:
      a: "${inputs.n}"
      b: 2.0
    save_as: doubled
outputs_map:
  result: "${doubled}"
""")
        validator = SequenceValidator(registry=reg)
        errors = validator.validate(seq)
        assert errors == []

        engine = SequenceEngine(registry=reg)
        out = engine.run(seq, inputs={"n": 5.0})
        assert out["result"] == 10.0

    def test_validation_catches_missing_brick(self) -> None:
        reg = BrickRegistry()
        loader = SequenceLoader()
        seq = loader.load_string("""
name: bad_seq
steps:
  - name: s1
    brick: nonexistent_brick
""")
        validator = SequenceValidator(registry=reg)
        with pytest.raises(SequenceValidationError) as exc_info:
            validator.validate(seq)
        # The brick name appears in the errors list
        assert any("nonexistent_brick" in e for e in exc_info.value.errors)

    def test_execution_error_propagates(self) -> None:
        reg = BrickRegistry()

        @brick()
        def always_fails(x: int) -> int:
            raise RuntimeError("intentional failure")

        reg.register(
            "always_fails",
            always_fails,
            always_fails.__brick_meta__,  # type: ignore[attr-defined]
        )
        loader = SequenceLoader()
        seq = loader.load_string("""
name: failing_seq
steps:
  - name: bad_step
    brick: always_fails
    params:
      x: 1
""")
        engine = SequenceEngine(registry=reg)
        with pytest.raises(BrickExecutionError) as exc_info:
            engine.run(seq)
        assert "always_fails" in str(exc_info.value)

    def test_validation_empty_registry_fails(self) -> None:
        reg = BrickRegistry()
        loader = SequenceLoader()
        seq = loader.load_string("""
name: seq_with_unknown
steps:
  - name: step1
    brick: unknown_op
""")
        validator = SequenceValidator(registry=reg)
        with pytest.raises(SequenceValidationError):
            validator.validate(seq)


class TestDiscoveryIntegration:
    def test_discover_and_run(self, tmp_path: Path) -> None:
        brick_file = tmp_path / "math_ops.py"
        brick_file.write_text(
            textwrap.dedent("""
                from bricks.core.brick import brick

                @brick(tags=["math"], description="Square a number")
                def square(x: float) -> float:
                    return x * x
            """).strip()
        )

        from bricks.core.discovery import BrickDiscovery

        reg = BrickRegistry()
        disc = BrickDiscovery(registry=reg)
        disc.discover_path(brick_file)
        assert reg.has("square")

        loader = SequenceLoader()
        seq = loader.load_string("""
name: square_seq
inputs:
  n: "float"
steps:
  - name: sq
    brick: square
    params:
      x: "${inputs.n}"
    save_as: squared
outputs_map:
  result: "${squared}"
""")
        engine = SequenceEngine(registry=reg)
        out = engine.run(seq, inputs={"n": 4.0})
        assert out["result"] == 16.0

    def test_discover_package_and_run(self, tmp_path: Path) -> None:
        pkg_dir = tmp_path / "ops"
        pkg_dir.mkdir()
        (pkg_dir / "adder.py").write_text(
            textwrap.dedent("""
                from bricks.core.brick import brick

                @brick(description="Add one to a number")
                def add_one(n: float) -> float:
                    return n + 1.0
            """).strip()
        )

        from bricks.core.discovery import BrickDiscovery

        reg = BrickRegistry()
        disc = BrickDiscovery(registry=reg)
        disc.discover_package(pkg_dir)
        assert reg.has("add_one")

        loader = SequenceLoader()
        seq = loader.load_string("""
name: add_one_seq
steps:
  - name: step
    brick: add_one
    params:
      n: 9.0
    save_as: result
outputs_map:
  out: "${result}"
""")
        engine = SequenceEngine(registry=reg)
        out = engine.run(seq)
        assert out["out"] == 10.0


class TestOutputsMap:
    def test_empty_outputs_map_returns_empty(self) -> None:
        reg = _make_math_registry()
        loader = SequenceLoader()
        seq = loader.load_string("""
name: no_outputs
steps:
  - name: step
    brick: add
    params:
      a: 1.0
      b: 2.0
""")
        engine = SequenceEngine(registry=reg)
        out = engine.run(seq)
        assert out == {}

    def test_multiple_outputs(self) -> None:
        reg = _make_math_registry()
        loader = SequenceLoader()
        seq = loader.load_string("""
name: multi_out
inputs:
  x: "float"
  y: "float"
steps:
  - name: s1
    brick: add
    params:
      a: "${inputs.x}"
      b: "${inputs.y}"
    save_as: sum_val
  - name: s2
    brick: multiply
    params:
      a: "${inputs.x}"
      b: "${inputs.y}"
    save_as: prod_val
outputs_map:
  sum: "${sum_val}"
  product: "${prod_val}"
""")
        engine = SequenceEngine(registry=reg)
        out = engine.run(seq, inputs={"x": 3.0, "y": 4.0})
        assert out["sum"] == 7.0
        assert out["product"] == 12.0

    def test_literal_output_value(self) -> None:
        """Outputs map with a literal value (no reference) passthrough."""
        reg = _make_math_registry()
        loader = SequenceLoader()
        seq = loader.load_string("""
name: literal_out
steps:
  - name: s1
    brick: add
    params:
      a: 5.0
      b: 5.0
    save_as: total
outputs_map:
  result: "${total}"
  label: "computed"
""")
        engine = SequenceEngine(registry=reg)
        out = engine.run(seq)
        assert out["result"] == 10.0
        assert out["label"] == "computed"


class TestLoaderIntegration:
    def test_load_string_and_run(self) -> None:
        reg = _make_math_registry()
        loader = SequenceLoader()
        seq = loader.load_string("""
name: round_test
steps:
  - name: r1
    brick: round_val
    params:
      value: 3.14159
      decimals: 2
    save_as: rounded
outputs_map:
  pi_approx: "${rounded}"
""")
        engine = SequenceEngine(registry=reg)
        out = engine.run(seq)
        assert out["pi_approx"] == 3.14

    def test_load_file_and_run(self, tmp_path: Path) -> None:
        seq_file = tmp_path / "test_seq.yaml"
        seq_file.write_text(
            textwrap.dedent("""
                name: file_load_test
                steps:
                  - name: step1
                    brick: add
                    params:
                      a: 100.0
                      b: 50.0
                    save_as: total
                outputs_map:
                  result: "${total}"
            """).strip()
        )
        reg = _make_math_registry()
        loader = SequenceLoader()
        seq = loader.load_file(seq_file)
        engine = SequenceEngine(registry=reg)
        out = engine.run(seq)
        assert out["result"] == 150.0
