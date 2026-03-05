"""Tests for bricks.cli.main."""

from typer.testing import CliRunner

from bricks.cli.main import app

runner = CliRunner()


class TestCLI:
    def test_help_exits_zero(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0

    def test_no_args_shows_help(self) -> None:
        result = runner.invoke(app, [])
        assert "Usage" in result.output
