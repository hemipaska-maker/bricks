"""Typer CLI application with all Bricks commands."""

from __future__ import annotations

import typer

app = typer.Typer(
    name="bricks",
    help="Bricks - Deterministic sequencing engine for typed Python building blocks.",
    no_args_is_help=True,
)

new_app = typer.Typer(help="Scaffold new Bricks components.")
app.add_typer(new_app, name="new")


@app.command()
def init() -> None:
    """Scaffold a new Bricks project in the current directory."""
    typer.echo("bricks init: not yet implemented")
    raise typer.Exit(code=1)


@new_app.command("brick")
def new_brick(name: str) -> None:
    """Scaffold a new Brick module.

    Args:
        name: Name of the brick to create.
    """
    typer.echo(f"bricks new brick {name}: not yet implemented")
    raise typer.Exit(code=1)


@new_app.command("sequence")
def new_sequence(name: str) -> None:
    """Scaffold a new YAML sequence file.

    Args:
        name: Name of the sequence to create.
    """
    typer.echo(f"bricks new sequence {name}: not yet implemented")
    raise typer.Exit(code=1)


@app.command()
def check(file: str) -> None:
    """Lint a Brick module or sequence file.

    Args:
        file: Path to the file to check.
    """
    typer.echo(f"bricks check {file}: not yet implemented")
    raise typer.Exit(code=1)


@app.command()
def run(sequence: str) -> None:
    """Execute a sequence.

    Args:
        sequence: Path to the sequence YAML file.
    """
    typer.echo(f"bricks run {sequence}: not yet implemented")
    raise typer.Exit(code=1)


@app.command(name="dry-run")
def dry_run(sequence: str) -> None:
    """Validate a sequence without executing (dry run).

    Args:
        sequence: Path to the sequence YAML file.
    """
    typer.echo(f"bricks dry-run {sequence}: not yet implemented")
    raise typer.Exit(code=1)


@app.command(name="list")
def list_bricks() -> None:
    """Show all available Bricks and their schemas."""
    typer.echo("bricks list: not yet implemented")
    raise typer.Exit(code=1)


@app.command()
def compose(intent: str) -> None:
    """AI-compose a sequence from a natural language description.

    Args:
        intent: Natural language description of the desired sequence.
    """
    typer.echo(f"bricks compose {intent!r}: not yet implemented")
    raise typer.Exit(code=1)
