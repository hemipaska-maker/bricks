"""Tests for bricks.core.context."""

import pytest

from bricks.core.context import ExecutionContext


class TestExecutionContext:
    def test_initial_state(self) -> None:
        ctx = ExecutionContext(inputs={"voltage": 5.0})
        assert ctx.inputs == {"voltage": 5.0}
        assert ctx.results == {}
        assert ctx.step_index == 0

    def test_save_and_retrieve_result(self) -> None:
        ctx = ExecutionContext()
        ctx.save_result("measured", 4.95)
        assert ctx.results["measured"] == 4.95

    def test_get_variable_checks_results_first(self) -> None:
        ctx = ExecutionContext(inputs={"x": 1})
        ctx.save_result("x", 2)
        assert ctx.get_variable("x") == 2

    def test_get_variable_missing_raises(self) -> None:
        ctx = ExecutionContext()
        with pytest.raises(KeyError):
            ctx.get_variable("missing")
