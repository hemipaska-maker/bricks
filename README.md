# Bricks

[![CI](https://github.com/hemipaska-maker/bricks/actions/workflows/ci.yml/badge.svg)](https://github.com/hemipaska-maker/bricks/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**Bricks** is a deterministic automation engine for AI agents. Instead of generating Python code at runtime — expensive, non-deterministic, unvalidated — AI composes YAML Blueprints that wire together pre-tested, typed building blocks. The engine validates before execution, produces identical results every time, and Blueprints are reusable artifacts that run forever at zero AI cost.

**Why it matters:** In benchmarks with real API calls, Bricks used **83% fewer tokens** than code generation for repeated tasks, and produced **identical execution across every run** while code generation used 18 different variable names across 5 attempts at the same function. [See the benchmark &rarr;](benchmark/showcase/README.md)

---

## Table of Contents

- [Why Bricks](#why-bricks)
- [Benchmark Results](#benchmark-results)
- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Core Concepts](#core-concepts)
  - [Bricks](#bricks-1)
  - [Sequences (Blueprints)](#sequences-blueprints)
  - [Validation](#validation)
  - [Execution](#execution)
- [CLI Reference](#cli-reference)
- [Auto-Discovery](#auto-discovery)
- [Configuration](#configuration)
- [AI Composition](#ai-composition)
- [Examples](#examples)
- [Development](#development)

---

## Why Bricks

Today, when an AI agent needs to perform a task, it generates code from scratch every time. This creates three problems:

**Token cost scales linearly.** Every invocation pays full price — even for tasks the AI has done a hundred times before. There is no concept of "reuse."

**Every generation is different.** Ask the same model the same question five times and you get five different programs. Variable names change, error handling appears and disappears, docstrings vary. If you need predictable, auditable behavior — testing, compliance, CI/CD — this is a problem.

**No validation before execution.** Generated code runs and you hope it works. There is no dry-run, no schema check, no way to catch a bad function call before it hits production.

Bricks solves all three. The AI composes a YAML Blueprint from typed building block schemas. The engine validates every step before execution. The Blueprint is saved as a file and reused forever — identical execution, zero AI cost after the first call.

```
Code Generation:   Request → AI writes Python → Run it → Hope it works → Pay again next time
Bricks:            Request → AI picks Bricks → YAML Blueprint → Validate → Execute → Reuse forever
```

---

## Benchmark Results

Real API calls. Real token counts. No simulations.

| Scenario | Code Generation | Bricks | Savings |
|---|---|---|---|
| Simple calc (single call) | 671 tokens | 921 tokens | -37% (Bricks costs more) |
| API pipeline (single call) | 1,039 tokens | 1,025 tokens | ~even |
| **Reusable artifact (10 runs)** | **5,518 tokens** | **922 tokens** | **83% fewer tokens** |

**Determinism:** 5 identical code generation requests produced **18 distinct variable names** and **0 exact duplicate outputs**. The same Blueprint executed identically all 5 times.

Full methodology, raw data, and reproducible scripts: [benchmark/showcase/README.md](benchmark/showcase/README.md)

---

## Features

- **Typed building blocks** — decorate any Python function with `@brick` or subclass `BaseBrick`
- **YAML sequences** — compose bricks into readable, auditable pipelines
- **Full validation** — 7 checks catch bad references, missing bricks, and empty sequences before execution
- **`${variable}` interpolation** — wire step outputs into downstream step inputs
- **Auto-discovery** — scan a directory and register all bricks automatically
- **JSON schema export** — generate schemas for every registered brick
- **8-command CLI** — `init`, `new`, `check`, `run`, `dry-run`, `list`, `compose`
- **AI composition** — describe a sequence in plain English and let Claude generate the YAML
- **Benchmarked** — [real token savings and determinism proof](benchmark/showcase/README.md) with live API calls
- **290 tests**, mypy `--strict` clean, ruff clean

---

## Installation

```bash
# Core package
pip install -e .

# With dev tools (pytest, mypy, ruff)
pip install -e ".[dev]"

# With AI composition support
pip install -e ".[dev,ai]"
```

---

## Quick Start

### 1. Define bricks

```python
from bricks.core import brick, BrickRegistry

@brick(tags=["math"], description="Multiply two numbers")
def multiply(a: float, b: float) -> float:
    return a * b

@brick(tags=["math"], description="Round a float to N decimal places")
def round_value(value: float, decimals: int = 2) -> float:
    return round(value, decimals)

@brick(tags=["io"], description="Format a value with a label")
def format_label(value: float, label: str) -> str:
    return f"{label}: {value}"
```

### 2. Write a YAML sequence

```yaml
# sequences/area.yaml
name: calculate_area
description: "Compute and format a rectangle area"
inputs:
  width: "float"
  height: "float"
steps:
  - name: compute_area
    brick: multiply
    params:
      a: "${inputs.width}"
      b: "${inputs.height}"
    save_as: area

  - name: rounded_area
    brick: round_value
    params:
      value: "${area}"
      decimals: 2
    save_as: area_rounded

  - name: display
    brick: format_label
    params:
      value: "${area_rounded}"
      label: "Area (m²)"
    save_as: result

outputs_map:
  area: "${area_rounded}"
  display: "${result}"
```

### 3. Validate and run

```python
from bricks.core import SequenceLoader, SequenceValidator, SequenceEngine

registry = BrickRegistry()
# ... register bricks ...

loader = SequenceLoader()
sequence = loader.load_file("sequences/area.yaml")

validator = SequenceValidator(registry=registry)
errors = validator.validate(sequence)
assert errors == []

engine = SequenceEngine(registry=registry)
outputs = engine.run(sequence, inputs={"width": 7.5, "height": 4.2})
# {"area": 31.5, "display": "Area (m²): 31.5"}
```

---

## Core Concepts

### Bricks

A **brick** is a typed, named, callable unit of work. Two styles are supported:

**Function brick** (recommended for simple logic):

```python
from bricks.core import brick

@brick(tags=["hardware"], description="Read a sensor channel", destructive=False)
def read_temperature(channel: int) -> float:
    return sensor.read(channel)
```

**Class-based brick** (recommended for stateful or complex bricks):

```python
from bricks.core import BaseBrick

class ConvertTemperature(BaseBrick):
    """Convert Celsius to Fahrenheit."""

    class Meta:
        tags = ["conversion"]
        description = "Convert Celsius to Fahrenheit"

    def execute(self, celsius: float) -> float:
        return celsius * 9 / 5 + 32
```

### Sequences (Blueprints)

Sequences (also called Blueprints) are YAML files that wire bricks together using `${variable}` references:

| Reference | Resolves to |
|---|---|
| `${inputs.name}` | A declared sequence input |
| `${save_as_name}` | The result of a previous step |

Outputs are declared in `outputs_map` and returned by `SequenceEngine.run()`.

### Validation

`SequenceValidator.validate(sequence)` runs 7 checks without executing anything:

1. Sequence has at least one step
2. Every `brick:` name exists in the registry
3. No duplicate step names
4. `outputs_map` values reference known `save_as` names or inputs
5. `${inputs.X}` references are declared in `inputs:`
6. `${name}` references point to a *prior* step's `save_as` (no forward refs)
7. *(Placeholder)* Type compatibility between step outputs and inputs

### Execution

`SequenceEngine.run(sequence, inputs={})` executes steps in order, resolving `${...}` references at each step and collecting results into `outputs_map`.

---

## CLI Reference

```
bricks --help
```

| Command | Description |
|---|---|
| `bricks init` | Scaffold a new project (`bricks.config.yaml`, `sequences/`, `bricks_lib/`) |
| `bricks new brick <name>` | Generate a `@brick`-decorated stub in `bricks_lib/<name>.py` |
| `bricks new sequence <name>` | Generate a YAML sequence template in `sequences/` |
| `bricks check <file.yaml>` | Validate a sequence without executing |
| `bricks run <file.yaml> --input key=value` | Execute a sequence and print outputs |
| `bricks dry-run <file.yaml>` | Validate a sequence (alias for `check`) |
| `bricks list` | List all registered bricks with tags and descriptions |
| `bricks compose "<intent>"` | AI-generate a YAML sequence from natural language |

**Example:**

```bash
# Scaffold a new project
bricks init

# Create a new brick
bricks new brick calculate_tax

# Create a new sequence
bricks new sequence invoice_total

# Validate the sequence
bricks check sequences/invoice_total.yaml

# Run with inputs
bricks run sequences/invoice_total.yaml --input quantity=5 --input unit_price=12.0

# List registered bricks
bricks list
```

---

## Auto-Discovery

`BrickDiscovery` scans `.py` files in a directory and registers all `@brick`-decorated functions and `BaseBrick` subclasses automatically:

```python
from pathlib import Path
from bricks.core import BrickRegistry, BrickDiscovery

registry = BrickRegistry()
discovery = BrickDiscovery(registry=registry)
count = discovery.discover_package(Path("bricks_lib/"))
print(f"Discovered {count} bricks")
```

Enable auto-discovery in `bricks.config.yaml`:

```yaml
registry:
  auto_discover: true
  paths:
    - bricks_lib/
```

---

## Configuration

Create `bricks.config.yaml` in your project root (or run `bricks init`):

```yaml
version: "1"

registry:
  auto_discover: true
  paths:
    - bricks_lib/

sequences:
  base_dir: sequences/

ai:
  model: claude-3-5-sonnet-20241022
  max_tokens: 4096
```

Load it in Python:

```python
from bricks.core import ConfigLoader

config = ConfigLoader().load(Path("."))
print(config.ai.model)  # "claude-3-5-sonnet-20241022"
```

---

## AI Composition

With the `ai` extra installed (`pip install -e ".[ai]"`), describe a sequence in plain English and let Claude generate the YAML:

```python
from bricks.ai import SequenceComposer

composer = SequenceComposer(registry=registry, api_key="sk-ant-...")
sequence = composer.compose(
    "Multiply quantity by unit price, apply a fractional discount, "
    "round to 2 decimal places, and return a formatted label."
)
# Returns a validated SequenceDefinition ready to run
```

Or from the CLI:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
bricks compose "Calculate total price with discount and round to 2 decimal places"
```

Try the demo (no API key required):

```bash
python examples/ai_composer.py

# Live mode with a real API call
python examples/ai_composer.py --live --api-key sk-ant-...
```

---

## Examples

| File | Description |
|---|---|
| `examples/yaml_sequence.py` | Load and execute a YAML sequence end-to-end |
| `examples/class_based_brick.py` | Class-based bricks with `BaseBrick` |
| `examples/discovery_example.py` | Auto-discovery of bricks from a directory |
| `examples/ai_composer.py` | AI-powered sequence composition (demo + live) |
| `examples/sequences/power_cycle_test.yaml` | Reference hardware test sequence |
| `benchmark/showcase/` | Token savings & determinism benchmark with real API data |

```bash
python examples/yaml_sequence.py
python examples/class_based_brick.py
python examples/discovery_example.py
python examples/ai_composer.py       # demo mode, no key needed
```

---

## Development

```bash
# Run all 290 tests
pytest

# Run with verbose output
pytest -v

# Type check (strict)
mypy bricks --strict

# Lint
ruff check .

# Format
ruff format .
```

The CI pipeline runs automatically on every push and pull request, testing against Python 3.10, 3.11, and 3.12.

---

## License

MIT
