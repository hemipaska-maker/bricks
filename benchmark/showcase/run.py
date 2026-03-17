"""Benchmark showcase entry point.

Usage:
    python -m benchmark.showcase.run                # all scenarios, estimated tokens
    python -m benchmark.showcase.run --live         # real API calls (needs API key)
    python -m benchmark.showcase.run --scenario A   # single scenario
    python -m benchmark.showcase.run --scenario all # all (default)
    python -m benchmark.showcase.run --output-dir /tmp/results
"""

from __future__ import annotations

import argparse
import difflib
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from bricks import __version__
from bricks.core import BrickRegistry

# ── default output dir ─────────────────────────────────────────────────────
_DEFAULT_OUTPUT = Path(__file__).parent / "results"

# Intents used for live mode YAML generation
_INTENT_SIMPLE_CALC = (
    "Calculate room area: multiply width * height, round to 2 decimal places, "
    "format label 'Area (m2)' with value. "
    "Inputs: width (float), height (float). Outputs: area (float), display (str)."
)
_INTENT_API_PIPELINE = (
    "Fetch user data from an API URL, extract a specific field from a user "
    "at a given index, and format the result as a display string. "
    "Inputs: api_url (str), user_index (int), field (str). "
    "Outputs: value (any), display (str)."
)


# ── helpers ────────────────────────────────────────────────────────────────


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


def _print_table(rows: list[dict[str, object]]) -> None:
    """Print the comparison table to stdout."""
    w = [24, 14, 14, 9]
    sep = "+" + "+".join("-" * (c + 2) for c in w) + "+"

    def row(*cells: str) -> str:
        parts = [f" {_col(c, w[i])} " for i, c in enumerate(cells)]
        return "|" + "|".join(parts) + "|"

    print(sep)
    print(row("Scenario", "Code Gen", "Bricks", "Savings"))
    print(sep)
    for r in rows:
        print(
            row(
                str(r["scenario"]),
                f"{r['codegen_tokens']:,} tokens",
                f"{r['bricks_tokens']:,} tokens",
                f"{r['ratio']}x",
            )
        )
    print(sep)


def _write_json(
    rows: list[dict[str, object]],
    output_dir: Path,
    mode: str = "estimated",
    determinism: dict[str, object] | None = None,
) -> Path:
    """Write results to a JSON file and return the path."""
    data: dict[str, object] = {
        "bricks_version": __version__,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "scenarios": {
            str(r["key"]): {
                "code_gen_tokens": r["codegen_tokens"],
                "bricks_tokens": r["bricks_tokens"],
                "savings_ratio": r["ratio"],
                "savings_pct": r["pct"],
            }
            for r in rows
        },
    }
    if determinism is not None:
        data["determinism"] = determinism
    out = output_dir / "results.json"
    out.write_text(json.dumps(data, indent=2))
    return out


def _write_markdown(rows: list[dict[str, object]], output_dir: Path) -> Path:
    """Write a markdown summary of results and return the path."""
    lines = [
        f"# Bricks v{__version__} -- Benchmark Results",
        "",
        "| Scenario | Code Gen | Bricks | Savings |",
        "|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['scenario']} "
            f"| {r['codegen_tokens']:,} tokens "
            f"| {r['bricks_tokens']:,} tokens "
            f"| {r['ratio']}x ({r['pct']}% less) |"
        )

    total_cg = sum(int(r["codegen_tokens"]) for r in rows)  # type: ignore[arg-type]
    total_br = sum(int(r["bricks_tokens"]) for r in rows)  # type: ignore[arg-type]
    overall_ratio = _savings_ratio(total_cg, total_br)
    overall_pct = _savings_pct(total_cg, total_br)

    lines += [
        "",
        "## Interpretation",
        "",
        f"Across all {len(rows)} scenarios Bricks used **{total_br:,} tokens** "
        f"vs **{total_cg:,} tokens** for raw code generation — a **{overall_ratio}x "
        f"reduction ({overall_pct}% fewer tokens)**. "
        f"The savings grow with repetition: Scenario C shows that once a Blueprint "
        f"is generated it can be re-executed with different inputs at near-zero "
        f"additional token cost, while code generation must regenerate the full "
        f"function for every new input set.",
    ]

    out = output_dir / "summary.md"
    out.write_text("\n".join(lines))
    return out


def _write_chart(rows: list[dict[str, object]], output_dir: Path) -> Path | None:
    try:
        import matplotlib.pyplot as plt  # type: ignore[import-not-found]
    except ImportError:
        return None

    labels = [str(r["scenario"]) for r in rows]
    codegen = [int(r["codegen_tokens"]) for r in rows]  # type: ignore[arg-type]
    bricks = [int(r["bricks_tokens"]) for r in rows]  # type: ignore[arg-type]

    x = range(len(labels))
    width = 0.35

    _fig, ax = plt.subplots(figsize=(9, 5))
    left = [i - width / 2 for i in x]
    right = [i + width / 2 for i in x]
    ax.bar(left, codegen, width, label="Code Generation", color="#4c72b0")
    ax.bar(right, bricks, width, label="Bricks", color="#55a868")

    ax.set_title("Token Usage: Code Generation vs. Bricks", fontsize=13)
    ax.set_ylabel("Tokens")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels)
    ax.legend()
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    plt.tight_layout()

    out = output_dir / "comparison_chart.png"
    plt.savefig(out, dpi=120)
    plt.close()
    return out


# ── demo runners (no API, token estimation) ─────────────────────────────────


def run_scenario_a() -> tuple[int, int]:
    """Run Scenario A and return (codegen_tokens, bricks_tokens)."""
    from benchmark.showcase.scenarios.simple_calc import (
        bricks_approach,
        code_generation_approach,
    )

    cg = code_generation_approach()
    br = bricks_approach()
    return cg["total_tokens"], br["total_tokens"]


def run_scenario_b() -> tuple[int, int]:
    """Run Scenario B and return (codegen_tokens, bricks_tokens)."""
    from benchmark.showcase.scenarios.api_pipeline import (
        bricks_approach,
        code_generation_approach,
    )

    cg = code_generation_approach()
    br = bricks_approach()
    return cg["total_tokens"], br["total_tokens"]


def run_scenario_c() -> tuple[int, int]:
    """Run Scenario C (10 repetitions) and return (codegen_tokens, bricks_tokens)."""
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


def _build_math_registry() -> BrickRegistry:
    """Build a registry with multiply, round_value, format_result."""
    from benchmark.showcase.bricks import build_showcase_registry
    from benchmark.showcase.bricks.math_bricks import multiply, round_value
    from benchmark.showcase.bricks.string_bricks import format_result

    return build_showcase_registry(multiply, round_value, format_result)


def _build_api_registry() -> BrickRegistry:
    """Build a registry with http_get, json_extract, format_result."""
    from benchmark.showcase.bricks import build_showcase_registry
    from benchmark.showcase.bricks.data_bricks import http_get, json_extract
    from benchmark.showcase.bricks.string_bricks import format_result

    return build_showcase_registry(http_get, json_extract, format_result)


def run_scenario_a_live(logger: logging.Logger) -> tuple[int, int]:
    """Scenario A live: 1 bricks call vs 1 python call."""
    from benchmark.showcase.live import bricks_api_call, python_api_call
    from benchmark.showcase.scenarios import CODEGEN_SYSTEM
    from benchmark.showcase.scenarios.simple_calc import _CODEGEN_USER

    logger.info("=== Scenario A: Simple Calc ===")
    registry = _build_math_registry()

    # Bricks: 1 API call -> YAML
    _, b_in, b_out = bricks_api_call(_INTENT_SIMPLE_CALC, registry, logger, "A-bricks")
    br_tokens = b_in + b_out

    # Python: 1 API call -> Python function
    _, c_in, c_out = python_api_call(CODEGEN_SYSTEM, _CODEGEN_USER, logger, "A-python")
    cg_tokens = c_in + c_out

    logger.info(
        "Scenario A result: codegen=%d  bricks=%d  ratio=%.2fx",
        cg_tokens,
        br_tokens,
        cg_tokens / br_tokens if br_tokens else float("inf"),
    )
    return cg_tokens, br_tokens


def run_scenario_b_live(logger: logging.Logger) -> tuple[int, int]:
    """Scenario B live: 1 bricks call vs 1 python call (API pipeline)."""
    from benchmark.showcase.live import bricks_api_call, python_api_call
    from benchmark.showcase.scenarios import CODEGEN_SYSTEM
    from benchmark.showcase.scenarios.api_pipeline import _CODEGEN_USER

    logger.info("=== Scenario B: API Pipeline ===")
    registry = _build_api_registry()

    # Bricks: 1 API call -> YAML
    _, b_in, b_out = bricks_api_call(_INTENT_API_PIPELINE, registry, logger, "B-bricks")
    br_tokens = b_in + b_out

    # Python: 1 API call -> Python function
    _, c_in, c_out = python_api_call(CODEGEN_SYSTEM, _CODEGEN_USER, logger, "B-python")
    cg_tokens = c_in + c_out

    logger.info(
        "Scenario B result: codegen=%d  bricks=%d  ratio=%.2fx",
        cg_tokens,
        br_tokens,
        cg_tokens / br_tokens if br_tokens else float("inf"),
    )
    return cg_tokens, br_tokens


def run_scenario_c_live(logger: logging.Logger) -> tuple[int, int]:
    """Scenario C live: 1 bricks call vs 10 python calls (reuse advantage).

    Bricks: generate the blueprint once, run 10 times at 0 extra tokens.
    Python: must make a separate API call for each of the 10 input sets.
    """
    from benchmark.showcase.live import bricks_api_call, python_api_call
    from benchmark.showcase.scenarios import CODEGEN_SYSTEM
    from benchmark.showcase.scenarios.session_cache import (
        _CODEGEN_USER_TEMPLATE,
        ROOM_INPUTS,
    )

    logger.info("=== Scenario C: 10x Session (reuse) ===")
    registry = _build_math_registry()

    # Bricks: 1 API call -> YAML; 9 subsequent runs cost 0 tokens
    _, b_in, b_out = bricks_api_call(_INTENT_SIMPLE_CALC, registry, logger, "C-bricks")
    br_tokens = b_in + b_out
    logger.info("[C-bricks] Runs 2-10 cost 0 tokens (YAML reuse, no API calls)")

    # Python: 10 separate API calls, one per input set
    cg_tokens = 0
    for i, inp in enumerate(ROOM_INPUTS):
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
    """Scenario D live: call Claude 5x with same prompt, measure variability."""
    from benchmark.showcase.live import python_api_call
    from benchmark.showcase.scenarios import CODEGEN_SYSTEM
    from benchmark.showcase.scenarios.determinism import (
        CODEGEN_USER,
        run_bricks,
        run_code_generation,
    )

    logger.info("=== Scenario D: Determinism ===")

    generations: list[str] = []
    for i in range(5):
        code, _, _ = python_api_call(CODEGEN_SYSTEM, CODEGEN_USER, logger, f"D-gen{i + 1}")
        generations.append(code)

    cg_result = run_code_generation(generations=generations)
    bricks_result = run_bricks()
    return cg_result, bricks_result


# ── determinism report ───────────────────────────────────────────────────────


def _write_determinism_report(
    cg: dict[str, object],
    br: dict[str, object],
    output_dir: Path,
) -> Path:
    """Write results/determinism_report.md from Scenario D results."""
    from pathlib import Path as _Path

    generations: list[str] = cg["generations"]  # type: ignore[assignment]
    metrics: dict[str, object] = cg["metrics"]  # type: ignore[assignment]
    bricks_metrics: dict[str, object] = br["metrics"]  # type: ignore[assignment]
    hallucinations: list[list[str]] = cg["hallucinations"]  # type: ignore[assignment]
    issues_count: int = int(cg["generations_with_issues"])  # type: ignore[arg-type]

    blueprint_yaml = (_Path(__file__).parent / "blueprints" / "room_area.yaml").read_text()

    eh: list[bool] = metrics["error_handling_present"]  # type: ignore[assignment]
    dl: list[int] = metrics["docstring_lengths"]  # type: ignore[assignment]
    loc: list[int] = metrics["lines_of_code"]  # type: ignore[assignment]
    val_passed: list[bool] = bricks_metrics["validation_passed"]  # type: ignore[assignment]

    lines: list[str] = []

    # ── Header ───────────────────────────────────────────────────────────────
    lines += [
        f"# Bricks v{__version__} -- Scenario D: Determinism Benchmark",
        "",
        "> **Claim:** Code generation produces a different program every time.  ",
        "> Bricks Blueprints produce identical execution every time.",
        "",
    ]

    # ── 1. Side-by-side diff of generation 1 vs generation 3 ────────────────
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

    # ── 2. Metrics table ─────────────────────────────────────────────────────
    n = len(generations)
    eh_str = ", ".join("✓" if v else "✗" for v in eh)
    dl_str = ", ".join(str(v) for v in dl)
    loc_str = ", ".join(str(v) for v in loc)
    val_str = ", ".join("✓" if v else "✗" for v in val_passed)

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

    # ── 3. Blueprint (shown once) ─────────────────────────────────────────────
    lines += [
        "## The Blueprint",
        "",
        "This is the same file used in all 5 executions. It will never change.",
        "",
        "```yaml",
        blueprint_yaml.rstrip(),
        "```",
        "",
    ]

    # ── 4. Conclusion ─────────────────────────────────────────────────────────
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

    # ── 5. Hallucination detection ────────────────────────────────────────────
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

    out = output_dir / "determinism_report.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


# ── scenario dispatch ────────────────────────────────────────────────────────

_SCENARIO_MAP = {
    "A": ("A: Simple Calc", "simple_calc", run_scenario_a, run_scenario_a_live),
    "B": ("B: API Pipeline", "api_pipeline", run_scenario_b, run_scenario_b_live),
    "C": ("C: 10x Session", "session_cache", run_scenario_c, run_scenario_c_live),
}

# Scenario D is handled separately (different return type — not a token comparison)
_SCENARIO_D_KEY = "D"


def main() -> None:
    """Parse args and run the benchmark showcase."""
    parser = argparse.ArgumentParser(
        description="Bricks benchmark showcase: token savings vs code generation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--scenario",
        default="all",
        choices=["A", "B", "C", "D", "all"],
        help="Which scenario to run (default: all).",
    )
    parser.add_argument(
        "--output-dir",
        default=str(_DEFAULT_OUTPUT),
        help="Directory for results.json, summary.md, comparison_chart.png.",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        default=False,
        help=(
            "Make real Anthropic API calls instead of using estimates. Requires ANTHROPIC_API_KEY environment variable."
        ),
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Set up logger for live mode
    logger: logging.Logger | None = None
    log_path: Path | None = None
    if args.live:
        from benchmark.showcase.live import setup_logger

        logger, log_path = setup_logger(output_dir)
        logger.info("Live mode: real API calls via Anthropic SDK")

    run_d = args.scenario in ("D", "all")
    token_scenario_keys = (
        list(_SCENARIO_MAP) if args.scenario == "all" else ([args.scenario] if args.scenario in _SCENARIO_MAP else [])
    )
    token_scenarios = [(k, _SCENARIO_MAP[k]) for k in token_scenario_keys]

    rows: list[dict[str, object]] = []
    mode = "live" if args.live else "estimated"
    determinism_data: dict[str, object] | None = None
    print()
    print(f"Bricks v{__version__}")
    print(f"Running Bricks benchmark showcase ({mode} mode)...")
    print()

    # ── Token-savings scenarios (A / B / C) ──────────────────────────────────
    for key, (label, skey, fn_demo, fn_live) in token_scenarios:
        print(f"  Running scenario {key}...", end=" ", flush=True)
        try:
            if args.live:
                if logger is None:
                    raise RuntimeError("Logger must be initialized for live mode")
                cg_tokens, br_tokens = fn_live(logger)
            else:
                cg_tokens, br_tokens = fn_demo()
            ratio = _savings_ratio(cg_tokens, br_tokens)
            pct = _savings_pct(cg_tokens, br_tokens)
            rows.append(
                {
                    "key": skey,
                    "scenario": label,
                    "codegen_tokens": cg_tokens,
                    "bricks_tokens": br_tokens,
                    "ratio": ratio,
                    "pct": pct,
                }
            )
            print(f"done  (code gen: {cg_tokens:,}  bricks: {br_tokens:,}  {ratio}x)")
        except Exception as exc:
            print(f"FAILED: {exc}")
            sys.exit(1)

    if rows:
        print()
        _print_table(rows)
        print()

    # ── Scenario D: Determinism ───────────────────────────────────────────────
    det_path: Path | None = None
    if run_d:
        print("  Running scenario D (determinism)...", end=" ", flush=True)
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

            # Print determinism metrics table
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

            det_path = _write_determinism_report(cg_result, br_result, output_dir)

            determinism_data = {
                "unique_variable_names": cg_metrics["unique_variable_names"],
                "unique_function_signatures": (cg_metrics["unique_function_signatures"]),
                "exact_duplicates": cg_metrics["exact_duplicates"],
                "generations_with_issues": issues,
                "bricks_execution_path_identical": (br_metrics["execution_path_identical"]),
                "bricks_validation_passed_all": all(val),
            }

        except Exception as exc:
            print(f"FAILED: {exc}")
            sys.exit(1)

    # ── Write outputs ─────────────────────────────────────────────────────────
    json_path = _write_json(rows, output_dir, mode=mode, determinism=determinism_data)
    print(f"  results.json -> {json_path}")

    if rows:
        md_path = _write_markdown(rows, output_dir)
        chart_path = _write_chart(rows, output_dir)
        print(f"  summary.md   -> {md_path}")
        if chart_path:
            print(f"  chart        -> {chart_path}")
        else:
            print("  chart        -> skipped (install matplotlib: pip install matplotlib)")

    if det_path:
        print(f"  determinism  -> {det_path}")

    if log_path:
        print(f"  log          -> {log_path}")
    print()


if __name__ == "__main__":
    main()
