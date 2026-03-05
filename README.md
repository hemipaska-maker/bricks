# Bricks

Deterministic sequencing engine: typed Python building blocks composed into auditable YAML sequences.

## Installation

```bash
pip install -e ".[dev]"
```

## Quick Start

```python
from bricks.core import brick, BrickRegistry

registry = BrickRegistry()

@brick(tags=["math"], description="Add two numbers")
def add(a: float, b: float) -> float:
    return a + b

registry.register("add", add, add.__brick_meta__)
```

## Development

```bash
pytest                    # run tests
mypy bricks --strict      # type check
ruff check .              # lint
ruff format .             # format
bricks --help             # CLI
```

## License

MIT
