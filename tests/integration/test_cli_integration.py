"""Integration tests: CLI commands with real sequences."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from typer.testing import CliRunner

from bricks.cli.main import app

runner = CliRunner()


class TestCliEndToEnd:
    def test_init_then_scaffold_brick(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        r1 = runner.invoke(app, ["init"])
        assert r1.exit_code == 0
        r2 = runner.invoke(app, ["new", "brick", "my_op"])
        assert r2.exit_code == 0
        assert (tmp_path / "bricks_lib" / "my_op.py").exists()

    def test_init_then_scaffold_sequence(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        runner.invoke(app, ["init"])
        r = runner.invoke(app, ["new", "sequence", "my_flow"])
        assert r.exit_code == 0
        assert (tmp_path / "sequences" / "my_flow.yaml").exists()

    def test_list_with_auto_discover(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        bricks_dir = tmp_path / "my_bricks"
        bricks_dir.mkdir()
        (bricks_dir / "ops.py").write_text(
            textwrap.dedent("""
                from bricks.core.brick import brick

                @brick(tags=["math"], description="Square root")
                def sqrt_approx(x: float) -> float:
                    return x ** 0.5
            """).strip()
        )
        (tmp_path / "bricks.config.yaml").write_text(
            "registry:\n  auto_discover: true\n  paths:\n    - 'my_bricks/'\n"
        )
        r = runner.invoke(app, ["list"])
        assert r.exit_code == 0
        assert "sqrt_approx" in r.output

    def test_run_with_real_brick(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        bricks_dir = tmp_path / "bricks_lib"
        bricks_dir.mkdir()
        (bricks_dir / "math_ops.py").write_text(
            textwrap.dedent("""
                from bricks.core.brick import brick

                @brick(description="Multiply two numbers")
                def multiply(a: float, b: float) -> float:
                    return a * b
            """).strip()
        )
        (tmp_path / "bricks.config.yaml").write_text(
            "registry:\n  auto_discover: true\n  paths:\n    - 'bricks_lib/'\n"
        )
        seq_file = tmp_path / "mul.yaml"
        seq_file.write_text(
            textwrap.dedent("""
                name: mul_seq
                inputs:
                  a: "float"
                  b: "float"
                steps:
                  - name: mul_step
                    brick: multiply
                    params:
                      a: "${inputs.a}"
                      b: "${inputs.b}"
                    save_as: product
                outputs_map:
                  result: "${product}"
            """).strip()
        )
        r = runner.invoke(
            app, ["run", str(seq_file), "--input", "a=3.0", "--input", "b=4.0"]
        )
        assert r.exit_code == 0
        assert "mul_seq" in r.output
        assert "12.0" in r.output

    def test_check_and_dry_run_agree(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        bricks_dir = tmp_path / "bricks_lib"
        bricks_dir.mkdir()
        (bricks_dir / "adder.py").write_text(
            textwrap.dedent("""
                from bricks.core.brick import brick

                @brick(description="Add two numbers")
                def add(a: float, b: float) -> float:
                    return a + b
            """).strip()
        )
        (tmp_path / "bricks.config.yaml").write_text(
            "registry:\n  auto_discover: true\n  paths:\n    - 'bricks_lib/'\n"
        )
        seq_file = tmp_path / "add.yaml"
        seq_file.write_text(
            textwrap.dedent("""
                name: add_seq
                steps:
                  - name: s1
                    brick: add
                    params:
                      a: 1.0
                      b: 2.0
                    save_as: result
                outputs_map:
                  out: "${result}"
            """).strip()
        )
        r1 = runner.invoke(app, ["check", str(seq_file)])
        r2 = runner.invoke(app, ["dry-run", str(seq_file)])
        assert r1.exit_code == 0
        assert r2.exit_code == 0


class TestCliRunEndToEnd:
    """End-to-end run tests with real bricks and sequences."""

    def _setup_project(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        bricks_lib = tmp_path / "bricks_lib"
        bricks_lib.mkdir()
        (bricks_lib / "calculator.py").write_text(
            textwrap.dedent("""
                from bricks.core.brick import brick

                @brick(tags=["math"], description="Add two floats")
                def add(a: float, b: float) -> float:
                    return a + b

                @brick(tags=["math"], description="Subtract b from a")
                def subtract(a: float, b: float) -> float:
                    return a - b

                @brick(tags=["math"], description="Multiply two floats")
                def multiply(a: float, b: float) -> float:
                    return a * b
            """).strip()
        )
        (tmp_path / "bricks.config.yaml").write_text(
            "registry:\n  auto_discover: true\n  paths:\n    - 'bricks_lib/'\n"
        )

    def test_run_add_sequence(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._setup_project(tmp_path, monkeypatch)
        seq_file = tmp_path / "add_seq.yaml"
        seq_file.write_text(
            textwrap.dedent("""
                name: add_seq
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
            """).strip()
        )
        r = runner.invoke(
            app, ["run", str(seq_file), "--input", "x=10.0", "--input", "y=5.0"]
        )
        assert r.exit_code == 0
        assert "15.0" in r.output

    def test_run_chained_sequence(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._setup_project(tmp_path, monkeypatch)
        seq_file = tmp_path / "chain_seq.yaml"
        seq_file.write_text(
            textwrap.dedent("""
                name: chain_seq
                inputs:
                  a: "float"
                  b: "float"
                steps:
                  - name: sum_step
                    brick: add
                    params:
                      a: "${inputs.a}"
                      b: "${inputs.b}"
                    save_as: sum_val
                  - name: double_step
                    brick: multiply
                    params:
                      a: "${sum_val}"
                      b: 2.0
                    save_as: doubled
                outputs_map:
                  result: "${doubled}"
            """).strip()
        )
        r = runner.invoke(
            app, ["run", str(seq_file), "--input", "a=3.0", "--input", "b=4.0"]
        )
        assert r.exit_code == 0
        assert "14.0" in r.output  # (3+4)*2 = 14

    def test_list_shows_multiple_bricks(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._setup_project(tmp_path, monkeypatch)
        r = runner.invoke(app, ["list"])
        assert r.exit_code == 0
        assert "add" in r.output
        assert "subtract" in r.output
        assert "multiply" in r.output

    def test_check_valid_sequence(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._setup_project(tmp_path, monkeypatch)
        seq_file = tmp_path / "valid_seq.yaml"
        seq_file.write_text(
            textwrap.dedent("""
                name: valid_seq
                steps:
                  - name: s1
                    brick: add
                    params:
                      a: 1.0
                      b: 2.0
                    save_as: r
                outputs_map:
                  out: "${r}"
            """).strip()
        )
        r = runner.invoke(app, ["check", str(seq_file)])
        assert r.exit_code == 0
        assert "valid" in r.output

    def test_run_outputs_correct_values(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._setup_project(tmp_path, monkeypatch)
        seq_file = tmp_path / "sub_seq.yaml"
        seq_file.write_text(
            textwrap.dedent("""
                name: sub_seq
                inputs:
                  a: "float"
                  b: "float"
                steps:
                  - name: sub_step
                    brick: subtract
                    params:
                      a: "${inputs.a}"
                      b: "${inputs.b}"
                    save_as: diff
                outputs_map:
                  result: "${diff}"
            """).strip()
        )
        r = runner.invoke(
            app, ["run", str(seq_file), "--input", "a=10.0", "--input", "b=3.0"]
        )
        assert r.exit_code == 0
        assert "7.0" in r.output


class TestCliInitWorkflow:
    """Tests for the full init + use workflow."""

    def test_full_init_workflow(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test the complete workflow: init -> new brick -> new sequence -> run."""
        monkeypatch.chdir(tmp_path)

        # Step 1: init
        r_init = runner.invoke(app, ["init"])
        assert r_init.exit_code == 0
        assert (tmp_path / "bricks.config.yaml").exists()
        assert (tmp_path / "bricks_lib").is_dir()
        assert (tmp_path / "sequences").is_dir()

        # Step 2: scaffold a brick file (manually create working implementation)
        brick_file = tmp_path / "bricks_lib" / "adder.py"
        brick_file.write_text(
            textwrap.dedent("""
                from bricks.core.brick import brick

                @brick(description="Add two numbers")
                def add(a: float, b: float) -> float:
                    return a + b
            """).strip()
        )

        # Step 3: update config to auto-discover
        (tmp_path / "bricks.config.yaml").write_text(
            textwrap.dedent("""
                version: "1"
                registry:
                  auto_discover: true
                  paths:
                    - 'bricks_lib/'
                sequences:
                  base_dir: "sequences/"
            """).strip()
        )

        # Step 4: create sequence file
        seq_file = tmp_path / "sequences" / "add_seq.yaml"
        seq_file.write_text(
            textwrap.dedent("""
                name: add_seq
                steps:
                  - name: add_step
                    brick: add
                    params:
                      a: 5.0
                      b: 3.0
                    save_as: total
                outputs_map:
                  result: "${total}"
            """).strip()
        )

        # Step 5: check the sequence
        r_check = runner.invoke(app, ["check", str(seq_file)])
        assert r_check.exit_code == 0

        # Step 6: run the sequence
        r_run = runner.invoke(app, ["run", str(seq_file)])
        assert r_run.exit_code == 0
        assert "8.0" in r_run.output

    def test_list_shows_tags_and_description(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        bricks_lib = tmp_path / "bricks_lib"
        bricks_lib.mkdir()
        (bricks_lib / "tagged.py").write_text(
            textwrap.dedent("""
                from bricks.core.brick import brick

                @brick(tags=["math", "core"], description="Compute average")
                def average(a: float, b: float) -> float:
                    return (a + b) / 2.0
            """).strip()
        )
        (tmp_path / "bricks.config.yaml").write_text(
            "registry:\n  auto_discover: true\n  paths:\n    - 'bricks_lib/'\n"
        )
        r = runner.invoke(app, ["list"])
        assert r.exit_code == 0
        assert "average" in r.output
        assert "math" in r.output
        assert "Compute average" in r.output
