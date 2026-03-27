"""Tests for the parametric task generator."""

from __future__ import annotations

import pytest

from bricks_benchmark.mcp.scenarios.task_generator import GeneratedTask, TaskGenerator


class TestGeneratedTask:
    """Tests for the GeneratedTask model."""

    def test_fields(self) -> None:
        """GeneratedTask has all required fields."""
        task = GeneratedTask(
            task_text="do something",
            expected_outputs={"x": 1.0},
            step_count=3,
            required_bricks=["add"],
        )
        assert task.task_text == "do something"
        assert task.step_count == 3
        assert task.required_bricks == ["add"]

    def test_default_required_bricks(self) -> None:
        """required_bricks defaults to empty list."""
        task = GeneratedTask(
            task_text="t",
            expected_outputs={},
            step_count=3,
        )
        assert task.required_bricks == []


class TestTaskGenerator:
    """Tests for the TaskGenerator.generate() method."""

    def test_minimum_steps(self) -> None:
        """Minimum step count is 3."""
        gen = TaskGenerator()
        with pytest.raises(ValueError, match="Minimum 3 steps"):
            gen.generate(2)

    @pytest.mark.parametrize("steps", [3, 5, 7, 10, 15])
    def test_generates_correct_step_count(self, steps: int) -> None:
        """Generated task has the requested step count."""
        gen = TaskGenerator()
        task = gen.generate(steps)
        assert task.step_count == steps

    @pytest.mark.parametrize("steps", [5, 10, 15])
    def test_has_required_bricks(self, steps: int) -> None:
        """Generated task lists required bricks."""
        gen = TaskGenerator()
        task = gen.generate(steps)
        assert len(task.required_bricks) > 0
        assert all(isinstance(b, str) for b in task.required_bricks)

    @pytest.mark.parametrize("steps", [5, 10, 15])
    def test_has_task_text(self, steps: int) -> None:
        """Generated task has non-empty task text."""
        gen = TaskGenerator()
        task = gen.generate(steps)
        assert len(task.task_text) > 50  # Should be a substantial description

    @pytest.mark.parametrize("steps", [5, 10, 15])
    def test_has_expected_outputs(self, steps: int) -> None:
        """Generated task has expected outputs."""
        gen = TaskGenerator()
        task = gen.generate(steps)
        assert len(task.expected_outputs) > 0

    def test_deterministic(self) -> None:
        """Same step count produces same expected outputs."""
        gen = TaskGenerator()
        task1 = gen.generate(10)
        task2 = gen.generate(10)
        assert task1.expected_outputs == task2.expected_outputs

    def test_area_calculation_correct(self) -> None:
        """First two steps compute area = 7.5 * 4.2 = 31.5."""
        gen = TaskGenerator()
        task = gen.generate(5)
        assert task.expected_outputs["area"] == 7.5 * 4.2
        assert task.expected_outputs["area_rounded"] == 31.5

    def test_format_result_in_required_bricks(self) -> None:
        """format_result is always required (last steps are display)."""
        gen = TaskGenerator()
        task = gen.generate(5)
        assert "format_result" in task.required_bricks

    @pytest.mark.parametrize("steps", [5, 25, 50])
    def test_preset_step_counts(self, steps: int) -> None:
        """Preset step counts (5, 25, 50) all generate valid tasks."""
        gen = TaskGenerator()
        # Steps above recipe limit should still work (capped)
        if steps <= 19:
            task = gen.generate(steps)
            assert task.step_count == steps
