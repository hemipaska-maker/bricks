"""Write apples-to-apples benchmark results to JSON and Markdown."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bricks import __version__


def write_apples_json(
    apples_dir: Path,
    mode: str,
    a2_curve: list[dict[str, Any]],
    c2_reuse: dict[str, Any],
    d2_determinism: dict[str, Any],
) -> Path:
    """Write results.json and per-scenario detail files to apples_dir.

    Args:
        apples_dir: Output directory (created if absent).
        mode: ``"live"`` or ``"estimated"``.
        a2_curve: List of A2 sub-scenario comparison dicts.
        c2_reuse: C2 reuse comparison dict.
        d2_determinism: D2 determinism comparison dict.

    Returns:
        Path to the written ``results.json``.
    """
    apples_dir.mkdir(parents=True, exist_ok=True)

    data: dict[str, Any] = {
        "bricks_version": __version__,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "ai_model": "claude-haiku-4-5-20251001",
        "comparison_type": "apples_to_apples",
        "complexity_curve": {
            r["label"]: {
                "steps": r["steps"],
                "no_tools": r["no_tools"],
                "bricks": r["bricks"],
            }
            for r in a2_curve
        },
        "reuse": c2_reuse,
        "determinism": d2_determinism,
    }

    (apples_dir / "A2_complexity.json").write_text(json.dumps({"complexity_curve": a2_curve}, indent=2))
    (apples_dir / "C2_reuse.json").write_text(json.dumps(c2_reuse, indent=2))
    (apples_dir / "D2_determinism.json").write_text(json.dumps(d2_determinism, indent=2))

    out = apples_dir / "results.json"
    out.write_text(json.dumps(data, indent=2))
    return out


def write_apples_markdown(
    apples_dir: Path,
    a2_curve: list[dict[str, Any]],
    c2_reuse: dict[str, Any],
) -> Path:
    """Write summary.md to apples_dir.

    Args:
        apples_dir: Output directory (created if absent).
        a2_curve: List of A2 sub-scenario comparison dicts.
        c2_reuse: C2 reuse comparison dict.

    Returns:
        Path to the written ``summary.md``.
    """
    apples_dir.mkdir(parents=True, exist_ok=True)

    lines = [
        f"# Bricks v{__version__} -- Apples-to-Apples Benchmark",
        "",
        "Same agent · same task · same model · same system prompt.",
        "The only variable: whether Bricks MCP tools are available.",
        "",
        "## Scenario A2: Complexity Curve",
        "",
        "| Sub-scenario | Steps | No Tools (tokens) | Bricks (tokens) | Bricks turns |",
        "|---|---|---|---|---|",
    ]

    for r in a2_curve:
        nt = r["no_tools"]
        br = r["bricks"]
        lines.append(
            f"| {r['label']} | {r['steps']} | {nt['total_tokens']:,} | {br['total_tokens']:,} | {br['turns']} |"
        )

    nt_total: int = c2_reuse.get("no_tools", {}).get("total_tokens", 0)  # type: ignore[assignment]
    br_total: int = c2_reuse.get("bricks", {}).get("total_tokens", 0)  # type: ignore[assignment]

    lines += [
        "",
        "## Scenario C2: Reuse Economics",
        "",
        f"10 runs of the 6-step property price task: "
        f"**{br_total:,} tokens** (Bricks, first run only) vs "
        f"**{nt_total:,} tokens** (No Tools, code regenerated every run). "
        f"After the first run, Bricks reuses the Blueprint at 0 tokens per subsequent run.",
        "",
    ]

    out = apples_dir / "summary.md"
    out.write_text("\n".join(lines))
    return out
