"""Tests for bricks.core.engine."""

from __future__ import annotations

import pytest

from bricks.core.brick import brick
from bricks.core.engine import SequenceEngine
from bricks.core.exceptions import BrickExecutionError
from bricks.core.models import SequenceDefinition, StepDefinition
from bricks.core.registry import BrickRegistry


class TestSequenceEngine:
    def test_engine_creation(self) -> None:
        reg = BrickRegistry()
        engine = SequenceEngine(registry=reg)
        assert engine is not None


def _make_registry() -> BrickRegistry:
    """Create a registry with add and multiply bricks."""
    reg = BrickRegistry()

    @brick(description="Add two numbers")
    def add(a: float, b: float) -> float:
        return a + b

    @brick(description="Multiply two numbers")
    def multiply(a: float, b: float) -> float:
        return a * b

    reg.register("add", add, add.__brick_meta__)  # type: ignore[attr-defined]
    reg.register("multiply", multiply, multiply.__brick_meta__)  # type: ignore[attr-defined]
    return reg


class TestEngineRun:
    def test_single_step_with_literal_params(self) -> None:
        reg = _make_registry()
        engine = SequenceEngine(registry=reg)
        seq = SequenceDefinition(
            name="test",
            steps=[
                StepDefinition(
                    name="s1", brick="add", params={"a": 3.0, "b": 4.0}, save_as="total"
                )
            ],
            outputs_map={"result": "${total}"},
        )
        out = engine.run(seq)
        assert out["result"] == 7.0

    def test_empty_outputs_map_returns_empty(self) -> None:
        reg = _make_registry()
        engine = SequenceEngine(registry=reg)
        seq = SequenceDefinition(
            name="test",
            steps=[StepDefinition(name="s1", brick="add", params={"a": 1.0, "b": 2.0})],
        )
        out = engine.run(seq)
        assert out == {}

    def test_inputs_resolved_in_params(self) -> None:
        reg = _make_registry()
        engine = SequenceEngine(registry=reg)
        seq = SequenceDefinition(
            name="test",
            inputs={"x": "float", "y": "float"},
            steps=[
                StepDefinition(
                    name="s1",
                    brick="add",
                    params={"a": "${inputs.x}", "b": "${inputs.y}"},
                    save_as="sum",
                )
            ],
            outputs_map={"total": "${sum}"},
        )
        out = engine.run(seq, inputs={"x": 10.0, "y": 5.0})
        assert out["total"] == 15.0

    def test_chained_steps(self) -> None:
        reg = _make_registry()
        engine = SequenceEngine(registry=reg)
        seq = SequenceDefinition(
            name="chain",
            steps=[
                StepDefinition(
                    name="s1", brick="add", params={"a": 2.0, "b": 3.0}, save_as="first"
                ),
                StepDefinition(
                    name="s2",
                    brick="multiply",
                    params={"a": "${first}", "b": 2.0},
                    save_as="second",
                ),
            ],
            outputs_map={"result": "${second}"},
        )
        out = engine.run(seq)
        assert out["result"] == 10.0  # (2+3)*2

    def test_brick_exception_wrapped(self) -> None:
        reg = BrickRegistry()

        @brick()
        def broken(x: int) -> int:
            raise ValueError("intentional")

        reg.register("broken", broken, broken.__brick_meta__)  # type: ignore[attr-defined]
        engine = SequenceEngine(registry=reg)
        seq = SequenceDefinition(
            name="test",
            steps=[StepDefinition(name="s1", brick="broken", params={"x": 1})],
        )
        with pytest.raises(BrickExecutionError) as exc_info:
            engine.run(seq)
        assert "broken" in str(exc_info.value)

    def test_none_inputs_treated_as_empty(self) -> None:
        reg = _make_registry()
        engine = SequenceEngine(registry=reg)
        seq = SequenceDefinition(
            name="test",
            steps=[
                StepDefinition(
                    name="s1", brick="add", params={"a": 1.0, "b": 2.0}, save_as="r"
                )
            ],
            outputs_map={"result": "${r}"},
        )
        out = engine.run(seq, inputs=None)
        assert out["result"] == 3.0

    def test_step_without_save_as_result_not_accessible(self) -> None:
        reg = _make_registry()
        engine = SequenceEngine(registry=reg)
        seq = SequenceDefinition(
            name="test",
            steps=[
                # first step saves nothing
                StepDefinition(name="s1", brick="add", params={"a": 1.0, "b": 2.0}),
                # second step saves result
                StepDefinition(
                    name="s2", brick="add", params={"a": 5.0, "b": 5.0}, save_as="r"
                ),
            ],
            outputs_map={"result": "${r}"},
        )
        out = engine.run(seq)
        assert out["result"] == 10.0

    def test_multiple_outputs(self) -> None:
        reg = _make_registry()
        engine = SequenceEngine(registry=reg)
        seq = SequenceDefinition(
            name="test",
            steps=[
                StepDefinition(
                    name="s1", brick="add", params={"a": 3.0, "b": 4.0}, save_as="sum"
                ),
                StepDefinition(
                    name="s2",
                    brick="multiply",
                    params={"a": 3.0, "b": 4.0},
                    save_as="product",
                ),
            ],
            outputs_map={"sum": "${sum}", "product": "${product}"},
        )
        out = engine.run(seq)
        assert out["sum"] == 7.0
        assert out["product"] == 12.0

    def test_execution_error_has_correct_attributes(self) -> None:
        reg = BrickRegistry()

        @brick()
        def fails(x: int) -> int:
            raise RuntimeError("fail!")

        reg.register("fails", fails, fails.__brick_meta__)  # type: ignore[attr-defined]
        engine = SequenceEngine(registry=reg)
        seq = SequenceDefinition(
            name="test",
            steps=[StepDefinition(name="my_step", brick="fails", params={"x": 1})],
        )
        with pytest.raises(BrickExecutionError) as exc_info:
            engine.run(seq)
        err = exc_info.value
        assert err.brick_name == "fails"
        assert err.step_name == "my_step"
        assert isinstance(err.cause, RuntimeError)
