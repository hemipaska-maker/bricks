"""Benchmark showcase entry point — CRM unified Engine pipeline.

BricksEngine and RawLLMEngine receive identical input.
Both are evaluated with the same check_correctness() function.
Only the system under test changes.

Usage:
    python -m bricks_benchmark.showcase.run --live                         # all CRM scenarios, default model
    python -m bricks_benchmark.showcase.run --live --scenario CRM-pipeline
    python -m bricks_benchmark.showcase.run --live --model gpt-4o-mini     # OpenAI
    python -m bricks_benchmark.showcase.run --live --model gemini/gemini-2.0-flash
    python -m bricks_benchmark.showcase.run --live --model ollama/llama3   # local, no API key
    python -m bricks_benchmark.showcase.run --live --claudecode            # ClaudeCode compose + default baseline
    python -m bricks_benchmark.showcase.run --live --claudecode --model gpt-4o-mini  # ClaudeCode + GPT baseline
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

from bricks import __version__

from bricks_benchmark.constants import DEFAULT_MODEL
from bricks_benchmark.showcase.formatters import print_cost_summary
from bricks_benchmark.showcase.metadata import make_run_dir, write_metadata

_run_logger = logging.getLogger("bricks_benchmark.showcase.run")

# ── default output dir ─────────────────────────────────────────────────────
_DEFAULT_OUTPUT = Path(__file__).parent / "results"

# Valid --scenario values
CRM_SCENARIOS = {"CRM-pipeline", "CRM-hallucination", "CRM-reuse"}
VALID_SCENARIOS = {"all"} | CRM_SCENARIOS


# ── scenario expansion ──────────────────────────────────────────────────────


def expand_scenarios(raw: list[str]) -> list[str]:
    """Expand scenario names into individual sub-scenario labels.

    Args:
        raw: List of scenario names from CLI (e.g. ``['all']``, ``['CRM-pipeline']``).

    Returns:
        De-duplicated, ordered list of individual scenario labels.
    """
    order: list[str] = ["CRM-pipeline", "CRM-hallucination", "CRM-reuse"]
    selected: set[str] = set()

    for s in raw:
        if s == "all":
            selected.update(order)
        else:
            selected.add(s)

    known = [s for s in order if s in selected]
    extra = [s for s in selected if s not in order]
    return known + extra


# ── helpers ──────────────────────────────────────────────────────────────────


def validate_model_env(model: str) -> None:
    """Warn if the expected API key for a model is missing from the environment.

    This is a best-effort check — LiteLLM may resolve the key from other sources.
    Ollama and local models need no key and are silently skipped.

    Args:
        model: LiteLLM model string (e.g. 'gpt-4o-mini', 'gemini/gemini-2.0-flash').
    """
    if model.startswith("ollama/"):
        return

    provider_keys: dict[str, str] = {
        "claude": "ANTHROPIC_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "gpt": "OPENAI_API_KEY",
        "openai": "OPENAI_API_KEY",
        "gemini": "GOOGLE_API_KEY",
        "google": "GOOGLE_API_KEY",
    }
    for prefix, env_var in provider_keys.items():
        if model.startswith(prefix) or f"/{prefix}" in model:
            if not os.environ.get(env_var):
                _run_logger.warning(
                    "Model %r typically requires %s — not found in environment",
                    model,
                    env_var,
                )
            return


def _build_litellm_provider(model: str) -> Any:
    """Return a LiteLLMProvider for the given model string.

    LiteLLM auto-detects the API key from environment variables.

    Args:
        model: LiteLLM model string.

    Returns:
        A LiteLLMProvider instance.
    """
    from bricks.llm.litellm_provider import LiteLLMProvider

    return LiteLLMProvider(model=model)


def _build_providers(claudecode: bool, model: str) -> tuple[Any, Any]:
    """Return (compose_provider, baseline_provider) for the two engines.

    Design:
    - BricksEngine always uses compose_provider (ClaudeCode if --claudecode).
    - RawLLMEngine always uses baseline_provider (LiteLLM with --model).
    - If --claudecode without --model, baseline uses DEFAULT_MODEL.

    Args:
        claudecode: If True, BricksEngine routes through ClaudeCodeProvider.
        model: LiteLLM model string for RawLLMEngine (and BricksEngine when not claudecode).

    Returns:
        Tuple of (compose_provider, baseline_provider).
    """
    baseline_provider = _build_litellm_provider(model)

    if claudecode:
        from bricks_provider_claudecode import ClaudeCodeProvider  # type: ignore[import-untyped]

        compose_provider = ClaudeCodeProvider(timeout=300)
    else:
        compose_provider = baseline_provider

    return compose_provider, baseline_provider


# ── main runner ─────────────────────────────────────────────────────────────


def run_benchmark(
    scenarios: list[str],
    run_dir: Path,
    logger: logging.Logger,
    claudecode: bool = False,
    model: str = DEFAULT_MODEL,
) -> None:
    """Run the CRM benchmark with both engines on each scenario.

    Args:
        scenarios: List of CRM scenario labels.
        run_dir: Timestamped run directory.
        logger: Logger for recording progress.
        claudecode: If True, BricksEngine uses ClaudeCodeProvider for compose.
        model: LiteLLM model string for LiteLLMProvider (and RawLLMEngine baseline).
    """
    from bricks_benchmark.showcase.crm_scenario import (
        run_crm_hallucination,
        run_crm_pipeline,
        run_crm_reuse,
    )
    from bricks_benchmark.showcase.engine import BricksEngine, RawLLMEngine

    compose_provider, baseline_provider = _build_providers(claudecode, model)
    bricks_engine = BricksEngine(provider=compose_provider)
    llm_engine = RawLLMEngine(provider=baseline_provider)

    t0 = time.monotonic()

    for crm_label in scenarios:
        logger.info("=== %s ===", crm_label)
        if crm_label == "CRM-pipeline":
            run_crm_pipeline(bricks_engine, llm_engine, run_dir)
        elif crm_label == "CRM-hallucination":
            run_crm_hallucination(bricks_engine, llm_engine, run_dir)
        elif crm_label == "CRM-reuse":
            run_crm_reuse(bricks_engine, llm_engine, run_dir)

    elapsed = time.monotonic() - t0
    print_cost_summary(0, 0, elapsed)


# ── logger setup ────────────────────────────────────────────────────────────


def _setup_logger(run_dir: Path) -> logging.Logger:
    """Create dual-output loggers: file (DEBUG) and console (INFO).

    Configures root loggers for all Bricks namespaces so every child logger
    (``bricks.ai.composer``, ``bricks_provider_claudecode.provider``, etc.)
    writes to the same ``benchmark_live.log`` and console stream.

    Args:
        run_dir: Directory where ``benchmark_live.log`` will be written.

    Returns:
        The ``bricks`` root logger.
    """
    log_path = run_dir / "benchmark_live.log"

    file_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s — %(message)s")
    console_fmt = logging.Formatter("[%(levelname)s] %(message)s")

    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(file_fmt)

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(console_fmt)

    for name in ("bricks", "bricks_provider_claudecode", "bricks_benchmark"):
        lg = logging.getLogger(name)
        lg.setLevel(logging.DEBUG)
        lg.handlers.clear()
        lg.propagate = False
        lg.addHandler(fh)
        lg.addHandler(ch)

    return logging.getLogger("bricks")


# ── CLI ─────────────────────────────────────────────────────────────────────


def main() -> None:
    """Parse args and run the CRM benchmark."""
    parser = argparse.ArgumentParser(
        description="Bricks CRM benchmark: BricksEngine vs RawLLMEngine, same input, same checker.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python -m bricks_benchmark.showcase.run --live\n"
            "  python -m bricks_benchmark.showcase.run --live --model gpt-4o-mini\n"
            "  python -m bricks_benchmark.showcase.run --live --model gemini/gemini-2.0-flash\n"
            "  python -m bricks_benchmark.showcase.run --live --model ollama/llama3\n"
            "  python -m bricks_benchmark.showcase.run --live --claudecode\n"
            "  python -m bricks_benchmark.showcase.run --live --claudecode --model gpt-4o-mini\n"
        ),
    )
    parser.add_argument(
        "--scenario",
        action="append",
        dest="scenarios",
        default=None,
        help=(
            "Which scenario(s) to run. Accepts: all (default), "
            "CRM-pipeline, CRM-hallucination, CRM-reuse. Can be specified multiple times."
        ),
    )
    parser.add_argument(
        "--model",
        type=str,
        default=DEFAULT_MODEL,
        help=(
            f"LiteLLM model string (default: {DEFAULT_MODEL}). "
            "Examples: gpt-4o-mini, gemini/gemini-2.0-flash, ollama/llama3. "
            "API key is read from the corresponding env var automatically."
        ),
    )
    parser.add_argument(
        "--output-dir",
        default=str(_DEFAULT_OUTPUT),
        help="Base directory for results (a timestamped subfolder is created inside).",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        default=False,
        help="Required. Make real LLM calls. Requires an API key (or --claudecode).",
    )
    parser.add_argument(
        "--claudecode",
        action="store_true",
        default=False,
        help=(
            "Use ClaudeCodeProvider (claude -p) for BricksEngine compose step. "
            "Zero cost on Max plan. RawLLMEngine still uses --model for fair comparison."
        ),
    )
    args = parser.parse_args()

    if not args.live:
        print()
        print("Error: --live is required. This benchmark makes real API calls.")
        print()
        print("Usage:")
        print("  python -m bricks_benchmark.showcase.run --live")
        print("  python -m bricks_benchmark.showcase.run --live --model gpt-4o-mini")
        print("  python -m bricks_benchmark.showcase.run --live --claudecode")
        print()
        print("API key is read from env (ANTHROPIC_API_KEY, OPENAI_API_KEY, etc.),")
        print("or use --claudecode for zero-cost runs inside a Claude Code session.")
        sys.exit(1)

    raw_scenarios = args.scenarios or ["all"]
    scenarios = expand_scenarios(raw_scenarios)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    run_dir = make_run_dir(output_dir)

    logger = _setup_logger(run_dir)

    if args.claudecode:
        compose_label = "ClaudeCodeProvider (claude -p)"
        baseline_label = f"LiteLLMProvider ({args.model})"
        if args.model == DEFAULT_MODEL:
            logger.info("--claudecode: BricksEngine via ClaudeCode, RawLLMEngine via %s", args.model)
        else:
            logger.info(
                "--claudecode + --model: BricksEngine via ClaudeCode, RawLLMEngine via %s",
                args.model,
            )
    else:
        compose_label = f"LiteLLMProvider ({args.model})"
        baseline_label = compose_label
        logger.info("Benchmark model: %s", args.model)
        validate_model_env(args.model)

    logger.info("Compose provider:   %s", compose_label)
    logger.info("Baseline provider:  %s", baseline_label)
    logger.info("Scenarios: %s", ", ".join(scenarios))
    logger.info("Bricks v%s", __version__)
    logger.info("Run folder: %s", run_dir)

    try:
        run_benchmark(scenarios, run_dir, logger, claudecode=args.claudecode, model=args.model)
    except Exception as exc:
        logger.error("FAILED: %s", exc, exc_info=True)
        sys.exit(1)

    write_metadata(run_dir, scenarios, model=args.model)
    print()


if __name__ == "__main__":
    main()
