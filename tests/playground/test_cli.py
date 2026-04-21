"""Tests for the ``bricks playground`` Typer subcommand."""

from __future__ import annotations

from unittest.mock import patch

from typer.testing import CliRunner

from bricks.cli.main import app

_runner = CliRunner()


def test_help_exits_zero() -> None:
    """``bricks playground --help`` must exit 0 (regardless of rich formatting)."""
    # Rich wraps option-table rows in CI's 80-col terminal, so we only assert
    # exit-zero here. The option list is verified by direct invocation in the
    # --no-browser / --force-port tests below.
    r = _runner.invoke(app, ["playground", "--help"])
    assert r.exit_code == 0


def test_playground_does_not_open_browser_with_flag() -> None:
    """``--no-browser`` must skip ``webbrowser.open``."""
    # uvicorn.run → return immediately instead of blocking.
    # webbrowser.open → record whether we called it.
    opened = {"called": False}

    def fake_open(_url: str) -> bool:
        opened["called"] = True
        return True

    def fake_run(*_args: object, **_kwargs: object) -> None:
        return None

    with (
        patch("uvicorn.run", new=fake_run),
        patch("webbrowser.open", new=fake_open),
    ):
        r = _runner.invoke(app, ["playground", "--no-browser", "--port", "0"])

    assert r.exit_code == 0
    assert opened["called"] is False


def test_playground_graceful_keyboard_interrupt() -> None:
    """Ctrl+C during uvicorn.run must not surface a traceback."""

    def raise_interrupt(*_args: object, **_kwargs: object) -> None:
        raise KeyboardInterrupt

    with (
        patch("uvicorn.run", new=raise_interrupt),
        patch("webbrowser.open"),
    ):
        r = _runner.invoke(app, ["playground", "--no-browser", "--port", "0"])

    assert r.exit_code == 0


def test_force_port_conflict_exits_1() -> None:
    """``--force-port`` on an occupied port fails fast with a non-zero exit."""
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        taken_port = sock.getsockname()[1]

        # uvicorn.run would try to bind — simulate the port-in-use error.
        def fake_run(*_args: object, **_kwargs: object) -> None:
            raise OSError(f"Port {taken_port} already in use")

        with patch("uvicorn.run", new=fake_run), patch("webbrowser.open"):
            r = _runner.invoke(
                app,
                ["playground", "--no-browser", "--port", str(taken_port), "--force-port"],
            )

    # The OSError escapes uvicorn.run → Typer surfaces a non-zero exit.
    assert r.exit_code != 0
