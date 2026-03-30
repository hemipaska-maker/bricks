# Contributing to Bricks

Thanks for your interest in contributing to Bricks!

## Getting Started

1. Fork the repo and clone it
2. Install in dev mode:
   ```bash
   pip install -e "packages/core[dev,ai]"
   pip install -e "packages/stdlib"
   pip install -e "packages/benchmark"
   ```
3. Run the test suite: `pytest`
4. Run linting: `ruff check . && ruff format --check . && mypy packages/core/src/bricks --strict`

## Making Changes

- Create a feature branch from `main`
- Write tests for new functionality
- Make sure all checks pass before submitting a PR
- Keep PRs focused — one feature or fix per PR

## Code Style

- Python 3.10+ with type hints everywhere
- Google-style docstrings on all public functions
- `ruff` for linting and formatting
- `mypy --strict` for type checking
- See `CLAUDE.md` for detailed code conventions

## Reporting Issues

Use GitHub Issues. Include:
- What you expected to happen
- What actually happened
- Steps to reproduce
- Python version and OS

## Questions?

Open a Discussion on GitHub.
