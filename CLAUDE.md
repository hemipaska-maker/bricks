# CLAUDE.md -- Bricks

## Project Overview

Bricks is a deterministic sequencing engine where typed Python building blocks (Bricks) are composed into auditable YAML sequences -- by engineers directly or by AI through natural language conversation -- with full validation before execution.

## Technical Constraints

- **Python 3.10+** -- use modern syntax (`X | Y` unions, `match`, etc.)
- **Runtime dependencies:** pydantic v2, typer, ruamel.yaml
- **Type hints everywhere** -- code must pass `mypy --strict`
- **Docstrings** -- all public classes, methods, and functions require clear docstrings
- **Pydantic v2** -- all data models use `pydantic.BaseModel`

## Public API

```python
from bricks.core import brick, BaseBrick, BrickModel, BrickRegistry

registry = BrickRegistry()

@brick(tags=["hardware"], destructive=False)
def read_temperature(channel: int) -> float:
    return sensor.read(channel)

registry.register("read_temperature", read_temperature, read_temperature.__brick_meta__)
```

### Key Behaviors

- `@brick(...)` -- decorator attaching metadata to a function brick
- `BaseBrick` -- abstract base class for class-based bricks with Meta/Input/Output inner classes
- `BrickRegistry` -- flat namespace; duplicate names raise `DuplicateBrickError`
- `SequenceEngine.run()` -- executes a `SequenceDefinition` step-by-step
- `SequenceValidator.validate()` -- dry-run validation without execution
- `ReferenceResolver` -- expands `${variable}` references in step parameters

## Monorepo Structure

```
bricks/                  # Python package root
  core/                  # Engine, context, validation, Brick base
    brick.py             # @brick decorator + BaseBrick + BrickModel
    registry.py          # BrickRegistry
    models.py            # Pydantic models (BrickMeta, StepDefinition, SequenceDefinition)
    engine.py            # SequenceEngine
    context.py           # ExecutionContext
    resolver.py          # ${variable} reference resolver
    validation.py        # Dry-run validation
    exceptions.py        # All custom exceptions
  cli/                   # Typer CLI commands
    main.py              # Typer app with command stubs
  ai/                    # AI composition layer
    composer.py          # SequenceComposer stub
tests/                   # Mirrors source structure
examples/                # Runnable standalone scripts
```

## Commands

```bash
# Run tests
pytest

# Type checking
mypy bricks --strict

# Lint
ruff check .

# Format
ruff format .

# Run CLI
bricks --help
```

## Code Conventions

- `snake_case` for functions/variables, `PascalCase` for classes
- Raise specific exceptions over generic ones -- no silent failures
- Keep modules small and focused -- one responsibility per file
- Tests mirror source structure in `tests/` (e.g., `tests/core/test_brick.py`)
- All exceptions inherit from `BrickError`
- Decorator returns unwrapped functions -- no behavior change
