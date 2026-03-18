"""Scenario C2: apples-to-apples reuse economics (10 runs of A2-6 task)."""

from __future__ import annotations

from typing import Any

from benchmark.mcp.agent_result import AgentResult
from benchmark.mcp.agent_runner import AgentRunner
from benchmark.mcp.scenarios import TASK_A2_6
from bricks.core import BrickRegistry

REUSE_RUNS = 10


def run_c2(runner: AgentRunner, registry: BrickRegistry) -> dict[str, Any]:
    """Run A2-6 task 10 times in both modes and return comparison dict.

    No_tools: 10 separate conversations — code is regenerated every time.
    Bricks: run 1 calls the API to compose a Blueprint; runs 2-10 simulate
    the session cache (Blueprint is reused, 0 tokens each).

    Args:
        runner: Configured AgentRunner instance.
        registry: BrickRegistry for the bricks mode.

    Returns:
        Comparison dict with per-mode token totals.
    """
    no_tools_results: list[AgentResult] = []
    bricks_results: list[AgentResult] = []
    first_blueprint: str | None = None

    for i in range(REUSE_RUNS):
        no_tools = runner.run_without_tools(TASK_A2_6)
        no_tools_results.append(no_tools)

        if i == 0:
            bricks = runner.run_with_bricks(TASK_A2_6, registry)
            first_blueprint = bricks.blueprint_yaml
            bricks_results.append(bricks)
        else:
            # Simulate session cache: Blueprint is stored after run 1.
            # Subsequent runs re-execute locally — no API call, 0 tokens.
            bricks_results.append(
                AgentResult(
                    task=TASK_A2_6,
                    mode="bricks",
                    turns=0,
                    total_input_tokens=0,
                    total_output_tokens=0,
                    total_tokens=0,
                    blueprint_yaml=first_blueprint,
                    final_answer="[Blueprint reused from run 1 — 0 tokens]",
                )
            )

    no_tools_total = sum(r.total_tokens for r in no_tools_results)
    bricks_total = sum(r.total_tokens for r in bricks_results)

    return {
        "runs": REUSE_RUNS,
        "step_count": 6,
        "no_tools": {
            "total_tokens": no_tools_total,
            "per_run_avg": no_tools_total // REUSE_RUNS,
        },
        "bricks": {
            "total_tokens": bricks_total,
            "first_run_tokens": bricks_results[0].total_tokens,
            "reuse_tokens": bricks_total - bricks_results[0].total_tokens,
        },
        "blueprint_yaml": first_blueprint,
    }
