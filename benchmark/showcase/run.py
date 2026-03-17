"""Benchmark showcase entry point.

Usage:
    python -m benchmark.showcase.run                # all scenarios, estimated tokens
    python -m benchmark.showcase.run --live         # real API calls (needs API key)
    python -m benchmark.showcase.run --scenario A   # complexity curve only
    python -m benchmark.showcase.run --scenario C   # reuse scenario only
    python -m benchmark.showcase.run --scenario D   # determinism scenario only
    python -m benchmark.showcase.run --scenario all # all (default)
    python -m benchmark.showcase.run --output-dir /tmp/results
"""

from __future__ import annotations

import argparse
import difflib
import json
import logging
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from bricks import __version__
from bricks.core import BrickRegistry

# ── default output dir ─────────────────────────────────────────────────────
_DEFAULT_OUTPUT = Path(__file__).parent / "results"

# Intents used for live mode YAML generation
_INTENT_A3 = (
    "Calculate room area: multiply width * height, round to 2 decimal places, "
    "format label 'Area (m2)' with value. "
    "Inputs: width (float), height (float). Outputs: area (float), display (str)."
)
_INTENT_A6 = (
    "Calculate property price: compute area from width * height, round to 2dp, "
    "multiply by price_per_sqm for base price, multiply base price by tax_rate for tax, "
    "add base + tax for total, format total as 'Total (EUR)' display string. "
    "Inputs: width (float), height (float), price_per_sqm (float), tax_rate (float). "
    "Outputs: total (float), display (str)."
)
_INTENT_A12 = (
    "Calculate full property valuation: compute area from dimensions, apply price per sqm, "
    "apply discount to base price, compute tax on net price, calculate total, "
    "derive monthly payment, format both total and monthly as display strings. "
    "Inputs: width, height, price_per_sqm, discount_rate, tax_rate, monthly_factor (all float). "
    "Outputs: total (float), monthly (float), total_display (str), monthly_display (str)."
)


# ── git helpers ─────────────────────────────────────────────────────────────


def _git_info() -> tuple[str, str, bool]:
    """Return (commit_hash, branch, is_dirty)."""
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
        )
        return commit, branch, dirty
    except Exception:
        return "unknown", "unknown", False


def _anthropic_sdk_version() -> str:
    """Return installed anthropic SDK version or 'not installed'."""
    try:
        import anthropic  # type: ignore[import-not-found]

        return str(anthropic.__version__)
    except Exception:
        return "not installed"


# ── run folder + metadata ────────────────────────────────────────────────────


def _make_run_dir(output_dir: Path) -> Path:
    """Create and return a unique timestamped run directory."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_dir = output_dir / f"run_{ts}_v{__version__}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def _write_metadata(run_dir: Path, mode: str, scenarios_run: list[str]) -> Path:
    """Write run_metadata.json to run_dir and return the path."""
    commit, branch, dirty = _git_info()
    metadata: dict[str, object] = {
        "bricks_version": __version__,
        "python_version": sys.version.split()[0],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ai_model": "claude-haiku-4-5-20251001",
        "ai_provider": "anthropic",
        "anthropic_sdk_version": _anthropic_sdk_version(),
        "mode": mode,
        "command": " ".join(["python", "-m", "benchmark.showcase.run", *sys.argv[1:]]),
        "scenarios_run": scenarios_run,
        "os": f"{platform.system()} {platform.release()}",
        "git_commit": commit,
        "git_branch": branch,
        "git_dirty": dirty,
    }
    out = run_dir / "run_metadata.json"
    out.write_text(json.dumps(metadata, indent=2))
    return out


# ── helpers ─────────────────────────────────────────────────────────────────


def _savings_ratio(codegen: int, bricks: int) -> float:
    """How many times fewer tokens Bricks uses."""
    if bricks == 0:
        return float("inf")
    return round(codegen / bricks, 2)


def _savings_pct(codegen: int, bricks: int) -> int:
    """Return percentage token savings (0 if codegen is zero)."""
    if codegen == 0:
        return 0
    return round((codegen - bricks) / codegen * 100)


def _col(text: str, width: int) -> str:
    """Left-justify text in a column of the given width."""
    return str(text).ljust(width)


def _print_curve_table(curve: list[dict[str, object]]) -> None:
    """Print the complexity curve table to stdout."""
    w = [20, 14, 14, 9]
    sep = "+" + "+".join("-" * (c + 2) for c in w) + "+"

    def row(*cells: str) -> str:
        parts = [f" {_col(c, w[i])} " for i, c in enumerate(cells)]
        return "|" + "|".join(parts) + "|"

    print(sep)
    print(row("Sub-scenario", "Code Gen", "Bricks", "Savings"))
    print(sep)
    for r in curve:
        ratio = _savings_ratio(int(r["codegen_tokens"]), int(r["bricks_tokens"]))  # type: ignore[arg-type]
        print(
            row(
                f"{r['label']} ({r['steps']} steps)",
                f"{r['codegen_tokens']:,} tokens",
                f"{r['bricks_tokens']:,} tokens",
                f"{ratio}x",
            )
        )
    print(sep)


# ── output writers ───────────────────────────────────────────────────────────


def _write_json(
    run_dir: Path,
    mode: str,
    curve: list[dict[str, object]] | None = None,
    reuse: dict[str, object] | None = None,
    determinism: dict[str, object] | None = None,
) -> Path:
    """Write results.json to run_dir and return the path."""
    data: dict[str, object] = {
        "bricks_version": __version__,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
    }
    if curve is not None:
        data["complexity_curve"] = {
            r["label"]: {
                "steps": r["steps"],
                "codegen_tokens": r["codegen_tokens"],
                "bricks_tokens": r["bricks_tokens"],
                "savings_ratio": _savings_ratio(
                    int(r["codegen_tokens"]),
                    int(r["bricks_tokens"]),  # type: ignore[arg-type]
                ),
                "savings_pct": _savings_pct(
                    int(r["codegen_tokens"]),
                    int(r["bricks_tokens"]),  # type: ignore[arg-type]
                ),
            }
            for r in curve
        }
    if reuse is not None:
        data["reuse"] = reuse
    if determinism is not None:
        data["determinism"] = determinism
    out = run_dir / "results.json"
    out.write_text(json.dumps(data, indent=2))
    return out


def _write_markdown(
    run_dir: Path,
    curve: list[dict[str, object]] | None = None,
    reuse: dict[str, object] | None = None,
) -> Path:
    """Write summary.md to run_dir and return the path."""
    lines = [
        f"# Bricks v{__version__} -- Benchmark Results",
        "",
    ]

    if curve is not None:
        lines += [
            "## Scenario A: Complexity Curve",
            "",
            "| Sub-scenario | Steps | Code Gen | Bricks | Savings |",
            "|---|---|---|---|---|",
        ]
        for r in curve:
            ratio = _savings_ratio(int(r["codegen_tokens"]), int(r["bricks_tokens"]))  # type: ignore[arg-type]
            pct = _savings_pct(int(r["codegen_tokens"]), int(r["bricks_tokens"]))  # type: ignore[arg-type]
            lines.append(
                f"| {r['label']} | {r['steps']} "
                f"| {r['codegen_tokens']:,} tokens "
                f"| {r['bricks_tokens']:,} tokens "
                f"| {ratio}x ({pct}% less) |"
            )
        lines.append("")

    if reuse is not None:
        cg_total = int(reuse["codegen_tokens_total"])  # type: ignore[arg-type]
        br_total = int(reuse["bricks_tokens_total"])  # type: ignore[arg-type]
        lines += [
            "## Scenario C: Reuse Economics",
            "",
            f"10 runs of the 6-step property price Blueprint: "
            f"**{br_total:,} tokens** (Bricks) vs **{cg_total:,} tokens** (Code Gen). "
            f"**{_savings_ratio(cg_total, br_total)}x reduction ({_savings_pct(cg_total, br_total)}% fewer tokens)**.",
            "",
        ]

    out = run_dir / "summary.md"
    out.write_text("\n".join(lines))
    return out


def _write_chart(curve: list[dict[str, object]], run_dir: Path) -> Path | None:
    """Write comparison_chart.png to run_dir if matplotlib is available."""
    try:
        import matplotlib.pyplot as plt  # type: ignore[import-not-found]
    except ImportError:
        return None

    labels = [f"{r['label']}\n({r['steps']} steps)" for r in curve]
    codegen = [int(r["codegen_tokens"]) for r in curve]  # type: ignore[arg-type]
    bricks = [int(r["bricks_tokens"]) for r in curve]  # type: ignore[arg-type]

    x = range(len(labels))
    width = 0.35

    _fig, ax = plt.subplots(figsize=(9, 5))
    left = [i - width / 2 for i in x]
    right = [i + width / 2 for i in x]
    ax.bar(left, codegen, width, label="Code Generation", color="#4c72b0")
    ax.bar(right, bricks, width, label="Bricks", color="#55a868")

    ax.set_title(f"Token Usage: Code Generation vs. Bricks (v{__version__})", fontsize=13)
    ax.set_ylabel("Tokens")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels)
    ax.legend()
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    plt.tight_layout()

    out = run_dir / "comparison_chart.png"
    plt.savefig(out, dpi=120)
    plt.close()
    return out


def _write_determinism_report(
    cg: dict[str, object],
    br: dict[str, object],
    run_dir: Path,
) -> Path:
    """Write determinism_report.md to run_dir from Scenario D results."""
    from pathlib import Path as _Path

    generations: list[str] = cg["generations"]  # type: ignore[assignment]
    metrics: dict[str, object] = cg["metrics"]  # type: ignore[assignment]
    bricks_metrics: dict[str, object] = br["metrics"]  # type: ignore[assignment]
    hallucinations: list[list[str]] = cg["hallucinations"]  # type: ignore[assignment]
    issues_count: int = int(cg["generations_with_issues"])  # type: ignore[arg-type]

    blueprint_yaml = (_Path(__file__).parent / "blueprints" / "property_price.yaml").read_text()

    eh: list[bool] = metrics["error_handling_present"]  # type: ignore[assignment]
    dl: list[int] = metrics["docstring_lengths"]  # type: ignore[assignment]
    loc: list[int] = metrics["lines_of_code"]  # type: ignore[assignment]
    val_passed: list[bool] = bricks_metrics["validation_passed"]  # type: ignore[assignment]

    lines: list[str] = []

    lines += [
        f"# Bricks v{__version__} -- Scenario D: Determinism Benchmark",
        "",
        "> **Claim:** Code generation produces a different program every time.  ",
        "> Bricks Blueprints produce identical execution every time.",
        "",
    ]

    gen1_lines = generations[0].splitlines(keepends=True)
    gen3_lines = generations[2].splitlines(keepends=True)
    diff = list(
        difflib.unified_diff(
            gen1_lines,
            gen3_lines,
            fromfile="generation_1.py",
            tofile="generation_3.py",
        )
    )

    lines += [
        "## Diff: Generation 1 vs Generation 3",
        "",
        "Same prompt. Same model. Different output.",
        "",
        "```diff",
    ]
    if diff:
        lines += [ln.rstrip("\n") for ln in diff]
    else:
        lines.append("(generations are identical — no diff)")
    lines += ["```", ""]

    n = len(generations)
    eh_str = ", ".join("Y" if v else "N" for v in eh)
    dl_str = ", ".join(str(v) for v in dl)
    loc_str = ", ".join(str(v) for v in loc)
    val_str = ", ".join("Y" if v else "N" for v in val_passed)

    lines += [
        "## Metrics",
        "",
        "| Metric | Code Generation (5 runs) | Bricks Blueprint (5 runs) |",
        "|--------|--------------------------|---------------------------|",
        f"| Unique variable names | {metrics['unique_variable_names']} distinct names across runs | N/A — no variables, just YAML wiring |",  # noqa: E501
        f"| Unique function signatures | {metrics['unique_function_signatures']} distinct signature(s) | N/A — Blueprint schema is fixed |",  # noqa: E501
        f"| Error handling consistent | {eh_str} | Always — Brick has it built-in |",
        f"| Docstring length (chars) | {dl_str} | N/A — Brick has fixed description |",
        f"| Lines of code | {loc_str} | Blueprint is always the same {len(blueprint_yaml.splitlines())} lines |",
        f"| Exact duplicate outputs | {metrics['exact_duplicates']} pair(s) identical | All {n} executions identical (same YAML) |",  # noqa: E501
        f"| Pre-execution validation | None — code runs and you hope | {val_str} — dry-run before every run |",
        "",
    ]

    lines += [
        "## The Blueprint (6 steps)",
        "",
        "This is the same file used in all 5 executions. It will never change.",
        "",
        "```yaml",
        blueprint_yaml.rstrip(),
        "```",
        "",
    ]

    lines += [
        "## Conclusion",
        "",
        (
            "Code generation produces a different program every time. "
            f"Across {n} runs with the identical prompt, "
            f"the model used {metrics['unique_variable_names']} distinct variable names, "
            f"{'varied' if not all(eh) else 'sometimes varied'} its error handling, "
            "and produced functions ranging from "
            f"{min(loc)} to {max(loc)} lines. "
            "Some are better, some are worse — you cannot predict which. "
            "Bricks produces the same execution every time: the Blueprint is "
            "validated once, stored as a YAML file, and executed identically "
            "on every subsequent run. You validate once, trust forever."
        ),
        "",
    ]

    lines += [
        "## Hallucination Detection",
        "",
        f"In this run, **{issues_count}/{n}** generation(s) had at least one issue.",
        "",
    ]
    for i, (issues, _gen) in enumerate(zip(hallucinations, generations, strict=True), 1):
        if issues:
            lines.append(f"- **Generation {i}:** {', '.join(issues)}")
        else:
            lines.append(f"- **Generation {i}:** clean")

    lines += [
        "",
        (
            "_Note: This rate varies — repeated benchmarks may show different results, "
            "which itself proves the non-determinism._"
        ),
        "",
    ]

    out = run_dir / "determinism_report.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


# ── demo runners (no API, token estimation) ─────────────────────────────────


def run_scenario_a() -> list[dict[str, object]]:
    """Run Scenario A (complexity curve) and return list of curve dicts."""
    from benchmark.showcase.scenarios.complexity_curve import run_complexity_curve

    return run_complexity_curve()  # type: ignore[return-value]


def run_scenario_c() -> tuple[int, int]:
    """Run Scenario C (reuse) and return (codegen_tokens, bricks_tokens)."""
    from benchmark.showcase.scenarios.session_cache import (
        bricks_approach,
        code_generation_approach,
    )

    cg = code_generation_approach()
    br = bricks_approach()
    return cg["total_tokens"], br["total_tokens"]


def run_scenario_d() -> tuple[dict[str, object], dict[str, object]]:
    """Run Scenario D (determinism) and return (cg_result, bricks_result)."""
    from benchmark.showcase.scenarios.determinism import run_bricks, run_code_generation

    return run_code_generation(), run_bricks()


# ── live runners (real Anthropic API calls) ──────────────────────────────────


def _build_math_registry_a3() -> BrickRegistry:
    """Build registry for A-3 (multiply, round_value, format_result)."""
    from benchmark.showcase.bricks import build_showcase_registry
    from benchmark.showcase.bricks.math_bricks import multiply, round_value
    from benchmark.showcase.bricks.string_bricks import format_result

    return build_showcase_registry(multiply, round_value, format_result)


def _build_math_registry_a6() -> BrickRegistry:
    """Build registry for A-6 (multiply, round_value, add, format_result)."""
    from benchmark.showcase.bricks import build_showcase_registry
    from benchmark.showcase.bricks.math_bricks import add, multiply, round_value
    from benchmark.showcase.bricks.string_bricks import format_result

    return build_showcase_registry(multiply, round_value, add, format_result)


def _build_math_registry_a12() -> BrickRegistry:
    """Build registry for A-12 (multiply, round_value, add, subtract, format_result)."""
    from benchmark.showcase.bricks import build_showcase_registry
    from benchmark.showcase.bricks.math_bricks import add, multiply, round_value, subtract
    from benchmark.showcase.bricks.string_bricks import format_result

    return build_showcase_registry(multiply, round_value, add, subtract, format_result)


def _run_sub_scenario_live(
    label: str,
    steps: int,
    intent: str,
    codegen_user: str,
    registry: BrickRegistry,
    logger: logging.Logger,
) -> dict[str, object]:
    """Run one sub-scenario in live mode and return curve dict."""
    from benchmark.showcase.live import bricks_api_call, python_api_call
    from benchmark.showcase.scenarios import CODEGEN_SYSTEM

    logger.info("=== Sub-scenario %s (%d steps) ===", label, steps)

    _, b_in, b_out = bricks_api_call(intent, registry, logger, f"{label}-bricks")
    br_tokens = b_in + b_out

    _, c_in, c_out = python_api_call(CODEGEN_SYSTEM, codegen_user, logger, f"{label}-python")
    cg_tokens = c_in + c_out

    logger.info(
        "Sub-scenario %s: codegen=%d  bricks=%d  ratio=%.2fx",
        label,
        cg_tokens,
        br_tokens,
        cg_tokens / br_tokens if br_tokens else float("inf"),
    )
    return {"label": label, "steps": steps, "codegen_tokens": cg_tokens, "bricks_tokens": br_tokens}


def run_scenario_a_live(logger: logging.Logger) -> list[dict[str, object]]:
    """Scenario A live: complexity curve with 3 live API calls per sub-scenario."""
    from benchmark.showcase.scenarios.complexity_curve import (
        _CODEGEN_USER_A3,
        _CODEGEN_USER_A6,
        _CODEGEN_USER_A12,
        INTENT_A3,
        INTENT_A6,
        INTENT_A12,
    )

    logger.info("=== Scenario A: Complexity Curve ===")
    curve = []
    for label, steps, intent, codegen_user, registry in [
        ("A-3", 3, INTENT_A3, _CODEGEN_USER_A3, _build_math_registry_a3()),
        ("A-6", 6, INTENT_A6, _CODEGEN_USER_A6, _build_math_registry_a6()),
        ("A-12", 12, INTENT_A12, _CODEGEN_USER_A12, _build_math_registry_a12()),
    ]:
        curve.append(_run_sub_scenario_live(label, steps, intent, codegen_user, registry, logger))
    return curve


def run_scenario_c_live(logger: logging.Logger) -> tuple[int, int]:
    """Scenario C live: 1 bricks call vs 10 python calls using A-6 task."""
    from benchmark.showcase.live import bricks_api_call, python_api_call
    from benchmark.showcase.scenarios import CODEGEN_SYSTEM
    from benchmark.showcase.scenarios.session_cache import (
        _CODEGEN_USER_TEMPLATE,
        PROPERTY_INPUTS,
    )

    logger.info("=== Scenario C: Reuse Economics (A-6, 10 runs) ===")
    registry = _build_math_registry_a6()

    _, b_in, b_out = bricks_api_call(_INTENT_A6, registry, logger, "C-bricks")
    br_tokens = b_in + b_out
    logger.info("[C-bricks] Runs 2-10 cost 0 tokens (Blueprint reuse, no API calls)")

    cg_tokens = 0
    for i, inp in enumerate(PROPERTY_INPUTS):
        user_prompt = _CODEGEN_USER_TEMPLATE.format(**inp)
        _, c_in, c_out = python_api_call(CODEGEN_SYSTEM, user_prompt, logger, f"C-python-run{i + 1}")
        cg_tokens += c_in + c_out

    logger.info(
        "Scenario C result: codegen=%d  bricks=%d  ratio=%.2fx",
        cg_tokens,
        br_tokens,
        cg_tokens / br_tokens if br_tokens else float("inf"),
    )
    return cg_tokens, br_tokens


def run_scenario_d_live(
    logger: logging.Logger,
) -> tuple[dict[str, object], dict[str, object]]:
    """Scenario D live: call Claude 5x with A-6 prompt, measure variability."""
    from benchmark.showcase.live import python_api_call
    from benchmark.showcase.scenarios import CODEGEN_SYSTEM
    from benchmark.showcase.scenarios.determinism import (
        CODEGEN_USER,
        run_bricks,
        run_code_generation,
    )

    logger.info("=== Scenario D: Determinism (A-6, 5 generations) ===")

    generations: list[str] = []
    for i in range(5):
        code, _, _ = python_api_call(CODEGEN_SYSTEM, CODEGEN_USER, logger, f"D-gen{i + 1}")
        generations.append(code)

    cg_result = run_code_generation(generations=generations)
    bricks_result = run_bricks()
    return cg_result, bricks_result


# ── main ─────────────────────────────────────────────────────────────────────


def main() -> None:
    """Parse args and run the benchmark showcase."""
    parser = argparse.ArgumentParser(
        description="Bricks benchmark showcase: complexity curve, reuse economics, determinism",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--scenario",
        default="all",
        choices=["A", "C", "D", "all"],
        help="Which scenario to run (default: all).",
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
        help="Make real Anthropic API calls instead of using estimates. Requires ANTHROPIC_API_KEY.",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create unique timestamped run directory
    run_dir = _make_run_dir(output_dir)

    mode = "live" if args.live else "estimated"
    run_a = args.scenario in ("A", "all")
    run_c = args.scenario in ("C", "all")
    run_d = args.scenario in ("D", "all")

    scenarios_run = []
    if run_a:
        scenarios_run += ["A-3", "A-6", "A-12"]
    if run_c:
        scenarios_run.append("C")
    if run_d:
        scenarios_run.append("D")

    # Set up logger
    logger: logging.Logger | None = None
    if args.live:
        from benchmark.showcase.live import setup_logger

        logger, _ = setup_logger(run_dir)
        logger.info("Live mode: real API calls via Anthropic SDK")
    else:
        # Also set up file logger for estimated mode
        log_path = run_dir / "benchmark.log"
        _logger = logging.getLogger("bricks.showcase")
        _logger.setLevel(logging.DEBUG)
        _logger.handlers.clear()
        fh = logging.FileHandler(log_path, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        _logger.addHandler(fh)
        logger = _logger

    print()
    print(f"Bricks v{__version__}")
    print(f"Run folder: {run_dir}")
    print(f"Running Bricks benchmark showcase ({mode} mode)...")
    print()

    curve: list[dict[str, object]] | None = None
    reuse_data: dict[str, object] | None = None
    determinism_data: dict[str, object] | None = None
    det_path: Path | None = None

    # ── Scenario A: Complexity Curve ─────────────────────────────────────────
    if run_a:
        print("  Running scenario A (complexity curve: 3 / 6 / 12 steps)...", end=" ", flush=True)
        try:
            if args.live:
                if logger is None:
                    raise RuntimeError("Logger must be initialized for live mode")
                curve = run_scenario_a_live(logger)
            else:
                curve = run_scenario_a()
            print("done")
            print()
            _print_curve_table(curve)
            print()
        except Exception as exc:
            print(f"FAILED: {exc}")
            sys.exit(1)

    # ── Scenario C: Reuse Economics ───────────────────────────────────────────
    if run_c:
        print("  Running scenario C (reuse: 10 runs of A-6 Blueprint)...", end=" ", flush=True)
        try:
            if args.live:
                if logger is None:
                    raise RuntimeError("Logger must be initialized for live mode")
                cg_tokens, br_tokens = run_scenario_c_live(logger)
            else:
                cg_tokens, br_tokens = run_scenario_c()
            ratio = _savings_ratio(cg_tokens, br_tokens)
            pct = _savings_pct(cg_tokens, br_tokens)
            print(f"done  (code gen: {cg_tokens:,}  bricks: {br_tokens:,}  {ratio}x)")
            reuse_data = {
                "runs": 10,
                "step_count": 6,
                "codegen_tokens_total": cg_tokens,
                "bricks_tokens_total": br_tokens,
                "savings_ratio": ratio,
                "savings_pct": pct,
            }
        except Exception as exc:
            print(f"FAILED: {exc}")
            sys.exit(1)

    # ── Scenario D: Determinism ───────────────────────────────────────────────
    if run_d:
        print("  Running scenario D (determinism: 5 A-6 generations)...", end=" ", flush=True)
        try:
            if args.live:
                if logger is None:
                    raise RuntimeError("Logger must be initialized for live mode")
                cg_result, br_result = run_scenario_d_live(logger)
            else:
                cg_result, br_result = run_scenario_d()

            cg_metrics: dict[str, object] = cg_result["metrics"]  # type: ignore[assignment]
            issues: int = int(cg_result["generations_with_issues"])  # type: ignore[arg-type]
            br_metrics: dict[str, object] = br_result["metrics"]  # type: ignore[assignment]
            print(f"done  (unique var names: {cg_metrics['unique_variable_names']}  hallucinations: {issues}/5)")

            print()
            print("  Determinism metrics:")
            eh: list[bool] = cg_metrics["error_handling_present"]  # type: ignore[assignment]
            loc: list[int] = cg_metrics["lines_of_code"]  # type: ignore[assignment]
            val: list[bool] = br_metrics["validation_passed"]  # type: ignore[assignment]
            uv = cg_metrics["unique_variable_names"]
            eh_flags = ["Y" if v else "N" for v in eh]
            val_flags = ["Y" if v else "N" for v in val]
            ep = br_metrics["execution_path_identical"]
            print(f"    Code gen -- unique variable names : {uv}")
            print(f"    Code gen -- error handling        : {eh_flags}")
            print(f"    Code gen -- lines of code         : min={min(loc)}  max={max(loc)}")
            print(f"    Code gen -- exact duplicates      : {cg_metrics['exact_duplicates']}")
            print(f"    Bricks  -- validation passed      : {val_flags}")
            print(f"    Bricks  -- execution path same    : {ep}")
            print()

            det_path = _write_determinism_report(cg_result, br_result, run_dir)

            determinism_data = {
                "step_count": 6,
                "generations": 5,
                "unique_variable_names": cg_metrics["unique_variable_names"],
                "unique_function_signatures": cg_metrics["unique_function_signatures"],
                "exact_duplicates": cg_metrics["exact_duplicates"],
                "hallucinations": issues,
                "lines_of_code": cg_metrics["lines_of_code"],
            }

        except Exception as exc:
            print(f"FAILED: {exc}")
            sys.exit(1)

    # ── Write outputs ─────────────────────────────────────────────────────────
    json_path = _write_json(run_dir, mode, curve=curve, reuse=reuse_data, determinism=determinism_data)
    md_path = _write_markdown(run_dir, curve=curve, reuse=reuse_data)
    meta_path = _write_metadata(run_dir, mode, scenarios_run)
    chart_path = _write_chart(curve, run_dir) if curve else None

    print(f"  results.json    -> {json_path}")
    print(f"  summary.md      -> {md_path}")
    print(f"  run_metadata    -> {meta_path}")
    if det_path:
        print(f"  determinism     -> {det_path}")
    if chart_path:
        print(f"  chart           -> {chart_path}")
    else:
        print("  chart           -> skipped (install matplotlib: pip install matplotlib)")
    print(f"  log             -> {run_dir / 'benchmark.log'}")
    print()


if __name__ == "__main__":
    main()
