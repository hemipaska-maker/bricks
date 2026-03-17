"""Tests for the benchmark showcase scenarios and bricks."""

from __future__ import annotations


class TestMathBricks:
    """Unit tests for showcase math bricks."""

    def test_multiply(self) -> None:
        from benchmark.showcase.bricks.math_bricks import multiply

        result = multiply(3.0, 4.0)
        assert result == {"result": 12.0}, f"Expected {{'result': 12.0}}, got {result!r}"

    def test_round_value(self) -> None:
        from benchmark.showcase.bricks.math_bricks import round_value

        result = round_value(3.14159, 2)
        assert result == {"result": 3.14}, f"Expected {{'result': 3.14}}, got {result!r}"

    def test_add(self) -> None:
        from benchmark.showcase.bricks.math_bricks import add

        result = add(3.0, 4.0)
        assert result == {"result": 7.0}, f"Expected {{'result': 7.0}}, got {result!r}"

    def test_subtract(self) -> None:
        from benchmark.showcase.bricks.math_bricks import subtract

        result = subtract(10.0, 3.0)
        assert result == {"result": 7.0}, f"Expected {{'result': 7.0}}, got {result!r}"

    def test_add_negative(self) -> None:
        from benchmark.showcase.bricks.math_bricks import add

        result = add(-1.0, 5.0)
        assert result == {"result": 4.0}, f"Expected {{'result': 4.0}}, got {result!r}"

    def test_subtract_negative_result(self) -> None:
        from benchmark.showcase.bricks.math_bricks import subtract

        result = subtract(3.0, 10.0)
        assert result == {"result": -7.0}, f"Expected {{'result': -7.0}}, got {result!r}"


class TestComplexityCurve:
    """Tests for Scenario A complexity curve."""

    def test_a3_returns_positive_tokens(self) -> None:
        from benchmark.showcase.scenarios.complexity_curve import bricks_a3, code_generation_a3

        cg = code_generation_a3()
        br = bricks_a3()
        assert cg["total_tokens"] > 0, f"Expected positive codegen tokens, got {cg['total_tokens']}"
        assert br["total_tokens"] > 0, f"Expected positive bricks tokens, got {br['total_tokens']}"

    def test_a6_returns_positive_tokens(self) -> None:
        from benchmark.showcase.scenarios.complexity_curve import bricks_a6, code_generation_a6

        cg = code_generation_a6()
        br = bricks_a6()
        assert cg["total_tokens"] > 0, f"Expected positive codegen tokens, got {cg['total_tokens']}"
        assert br["total_tokens"] > 0, f"Expected positive bricks tokens, got {br['total_tokens']}"

    def test_a12_returns_positive_tokens(self) -> None:
        from benchmark.showcase.scenarios.complexity_curve import bricks_a12, code_generation_a12

        cg = code_generation_a12()
        br = bricks_a12()
        assert cg["total_tokens"] > 0, f"Expected positive codegen tokens, got {cg['total_tokens']}"
        assert br["total_tokens"] > 0, f"Expected positive bricks tokens, got {br['total_tokens']}"

    def test_complexity_curve_has_three_entries(self) -> None:
        from benchmark.showcase.scenarios.complexity_curve import run_complexity_curve

        curve = run_complexity_curve()
        assert len(curve) == 3, f"Expected 3 entries, got {len(curve)}"

    def test_complexity_curve_labels(self) -> None:
        from benchmark.showcase.scenarios.complexity_curve import run_complexity_curve

        curve = run_complexity_curve()
        labels = [r["label"] for r in curve]
        assert labels == ["A-3", "A-6", "A-12"], f"Expected ['A-3', 'A-6', 'A-12'], got {labels!r}"

    def test_complexity_curve_steps_increase(self) -> None:
        from benchmark.showcase.scenarios.complexity_curve import run_complexity_curve

        curve = run_complexity_curve()
        steps = [r["steps"] for r in curve]
        assert steps == [3, 6, 12], f"Expected [3, 6, 12], got {steps!r}"

    def test_a6_executes_blueprint(self) -> None:
        from benchmark.showcase.scenarios.complexity_curve import bricks_a6

        br = bricks_a6()
        result = br["execution_result"]
        assert "total" in result, f"Expected 'total' in result, got keys: {list(result.keys())}"
        assert "display" in result, f"Expected 'display' in result, got keys: {list(result.keys())}"

    def test_a12_executes_blueprint(self) -> None:
        from benchmark.showcase.scenarios.complexity_curve import bricks_a12

        br = bricks_a12()
        result = br["execution_result"]
        assert "total" in result, f"Expected 'total' in result, got keys: {list(result.keys())}"
        assert "monthly" in result, f"Expected 'monthly' in result, got keys: {list(result.keys())}"


class TestScenarioC:
    """Tests for Scenario C reuse economics."""

    def test_code_generation_has_10_runs(self) -> None:
        from benchmark.showcase.scenarios.session_cache import code_generation_approach

        result = code_generation_approach()
        assert len(result["runs"]) == 10, f"Expected 10 runs, got {len(result['runs'])}"

    def test_bricks_approach_run1_has_tokens(self) -> None:
        from benchmark.showcase.scenarios.session_cache import bricks_approach

        result = bricks_approach()
        assert result["runs"][0]["total_tokens"] > 0, (
            f"Expected positive tokens for run 1, got {result['runs'][0]['total_tokens']}"
        )

    def test_bricks_approach_runs_2_to_10_are_zero(self) -> None:
        from benchmark.showcase.scenarios.session_cache import bricks_approach

        result = bricks_approach()
        for run in result["runs"][1:]:
            assert run["total_tokens"] == 0, f"Expected 0 tokens for run {run['run']}, got {run['total_tokens']}"

    def test_bricks_cheaper_than_codegen(self) -> None:
        from benchmark.showcase.scenarios.session_cache import bricks_approach, code_generation_approach

        cg = code_generation_approach()
        br = bricks_approach()
        assert br["total_tokens"] < cg["total_tokens"], (
            f"Expected bricks ({br['total_tokens']}) < codegen ({cg['total_tokens']})"
        )


class TestScenarioD:
    """Tests for Scenario D determinism."""

    def test_run_code_generation_returns_5_generations(self) -> None:
        from benchmark.showcase.scenarios.determinism import run_code_generation

        result = run_code_generation()
        assert len(result["generations"]) == 5, f"Expected 5 generations, got {len(result['generations'])}"

    def test_run_bricks_all_validations_pass(self) -> None:
        from benchmark.showcase.scenarios.determinism import run_bricks

        result = run_bricks()
        assert all(result["metrics"]["validation_passed"]), (
            f"Expected all validations to pass, got: {result['metrics']['validation_passed']}"
        )

    def test_run_bricks_execution_path_identical(self) -> None:
        from benchmark.showcase.scenarios.determinism import run_bricks

        result = run_bricks()
        assert result["metrics"]["execution_path_identical"] is True, "Expected execution_path_identical to be True"
