"""Benchmark showcase entry point.

Usage:
    python -m benchmark.showcase.run                # all scenarios, estimated tokens
    python -m benchmark.showcase.run --scenario A   # single scenario
    python -m benchmark.showcase.run --scenario all # all (default)
    python -m benchmark.showcase.run --output-dir /tmp/results
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── default output dir ─────────────────────────────────────────────────────
_DEFAULT_OUTPUT = Path(__file__).parent / "results"


# ── helpers ────────────────────────────────────────────────────────────────


def _savings_ratio(codegen: int, bricks: int) -> float:
    """How many times fewer tokens Bricks uses."""
    if bricks == 0:
        return float("inf")
    return round(codegen / bricks, 2)


def _savings_pct(codegen: int, bricks: int) -> int:
    if codegen == 0:
        return 0
    return round((codegen - bricks) / codegen * 100)


def _col(text: str, width: int) -> str:
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


def _write_json(rows: list[dict[str, object]], output_dir: Path) -> Path:
    data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": "estimated",
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
    out = output_dir / "results.json"
    out.write_text(json.dumps(data, indent=2))
    return out


def _write_markdown(rows: list[dict[str, object]], output_dir: Path) -> Path:
    lines = [
        "# Bricks Benchmark Results",
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

    fig, ax = plt.subplots(figsize=(9, 5))
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


# ── runner ─────────────────────────────────────────────────────────────────


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


_SCENARIO_MAP = {
    "A": ("A: Simple Calc", "simple_calc", run_scenario_a),
    "B": ("B: API Pipeline", "api_pipeline", run_scenario_b),
    "C": ("C: 10x Session", "session_cache", run_scenario_c),
}


def main() -> None:
    """Parse args and run the benchmark showcase."""
    parser = argparse.ArgumentParser(
        description="Bricks benchmark showcase: token savings vs code generation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--scenario",
        default="all",
        choices=["A", "B", "C", "all"],
        help="Which scenario to run (default: all).",
    )
    parser.add_argument(
        "--output-dir",
        default=str(_DEFAULT_OUTPUT),
        help="Directory for results.json, summary.md, comparison_chart.png.",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    scenarios = (
        list(_SCENARIO_MAP.items())
        if args.scenario == "all"
        else [(args.scenario, _SCENARIO_MAP[args.scenario])]
    )

    rows: list[dict[str, object]] = []
    print()
    print("Running Bricks benchmark showcase...")
    print()

    for key, (label, skey, fn) in scenarios:
        print(f"  Running scenario {key}...", end=" ", flush=True)
        try:
            cg_tokens, br_tokens = fn()
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

    print()
    _print_table(rows)
    print()

    # Write outputs
    json_path = _write_json(rows, output_dir)
    md_path = _write_markdown(rows, output_dir)
    chart_path = _write_chart(rows, output_dir)

    print(f"  results.json -> {json_path}")
    print(f"  summary.md   -> {md_path}")
    if chart_path:
        print(f"  chart        -> {chart_path}")
    else:
        print("  chart        -> skipped (install matplotlib: pip install matplotlib)")
    print()


if __name__ == "__main__":
    main()
