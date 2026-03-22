"""Tests for benchmark constants and enums."""

from __future__ import annotations

from benchmark.constants import (
    DEFAULT_MODEL,
    DETERMINISM_RUNS,
    REUSE_RUNS,
    RunMode,
    RunStatus,
    Scenario,
)


class TestScenarioEnum:
    """Tests for the Scenario enum."""

    def test_values(self) -> None:
        """Scenario enum has expected values."""
        assert Scenario.A.value == "A"
        assert Scenario.C.value == "C"
        assert Scenario.D.value == "D"

    def test_string_comparison(self) -> None:
        """Scenario values compare correctly with strings."""
        assert Scenario.A.value == "A"
        assert Scenario.C.value == "C"


class TestRunModeEnum:
    """Tests for the RunMode enum."""

    def test_values(self) -> None:
        """RunMode enum has expected values."""
        assert RunMode.TOOL_USE.value == "tool_use"
        assert RunMode.COMPOSE.value == "compose"


class TestRunStatusEnum:
    """Tests for the RunStatus enum."""

    def test_values(self) -> None:
        """RunStatus enum has expected values."""
        assert RunStatus.OK.value == "OK correct"
        assert RunStatus.WRONG.value == "WRONG silent"
        assert RunStatus.CAUGHT.value == "CAUGHT pre-exec"
        assert RunStatus.CLEAR.value == "CLEAR error"
        assert RunStatus.CRASH.value == "CRASH runtime"


class TestConstants:
    """Tests for shared constants."""

    def test_model_is_haiku(self) -> None:
        """Default model is Haiku."""
        assert "haiku" in DEFAULT_MODEL

    def test_reuse_runs(self) -> None:
        """REUSE_RUNS is 10."""
        assert REUSE_RUNS == 10

    def test_determinism_runs(self) -> None:
        """DETERMINISM_RUNS is 5."""
        assert DETERMINISM_RUNS == 5
