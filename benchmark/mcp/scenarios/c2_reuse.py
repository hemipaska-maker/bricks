"""Scenario C: apples-to-apples reuse economics (10 runs of the same task)."""

from __future__ import annotations

from typing import Any

from benchmark.constants import REUSE_RUNS
from benchmark.mcp.agent_result import AgentResult
from benchmark.mcp.agent_runner import AgentRunner, OnTurnCallback
from bricks.core import BrickRegistry


def run_c(
    runner: AgentRunner,
    task_text: str,
    registry: BrickRegistry,
    on_turn: OnTurnCallback = None,
) -> dict[str, Any]:
    """Run a task multiple times in both modes and return comparison dict.

    No_tools: all runs make separate API calls — code is regenerated every time.
    Bricks: run 1 calls the API to compose a Blueprint; runs 2-N simulate
    the session cache (Blueprint is reused, 0 tokens each).

    Args:
        runner: Configured AgentRunner instance.
        task_text: Task description.
        registry: BrickRegistry for the bricks mode.
        on_turn: Optional per-turn callback for logging.

    Returns:
        Comparison dict with per-mode token totals.
    """
    no_tools_results: list[AgentResult] = []
    bricks_results: list[AgentResult] = []
    first_blueprint: str | None = None

    for i in range(REUSE_RUNS):
        no_tools = runner.run_without_tools(task_text, on_turn=on_turn)
        no_tools_results.append(no_tools)

        if i == 0:
            bricks = runner.run_with_bricks(task_text, registry, on_turn=on_turn)
            first_blueprint = bricks.blueprint_yaml
            bricks_results.append(bricks)
        else:
            bricks_results.append(
                AgentResult(
                    task=task_text,
                    mode="bricks",
                    turns=0,
                    total_input_tokens=0,
                    total_output_tokens=0,
                    total_tokens=0,
                    blueprint_yaml=first_blueprint,
                    final_answer="[Blueprint reused from run 1 — 0 tokens]",
                )
            )

    nt_input = sum(r.total_input_tokens for r in no_tools_results)
    nt_output = sum(r.total_output_tokens for r in no_tools_results)
    br_input = sum(r.total_input_tokens for r in bricks_results)
    br_output = sum(r.total_output_tokens for r in bricks_results)

    return {
        "runs": REUSE_RUNS,
        "no_tools": {
            "total_tokens": nt_input + nt_output,
            "input_tokens": nt_input,
            "output_tokens": nt_output,
            "per_run_avg": (nt_input + nt_output) // REUSE_RUNS,
        },
        "bricks": {
            "total_tokens": br_input + br_output,
            "input_tokens": br_input,
            "output_tokens": br_output,
            "first_run_tokens": bricks_results[0].total_tokens,
            "reuse_tokens": (br_input + br_output) - bricks_results[0].total_tokens,
        },
        "blueprint_yaml": first_blueprint,
    }
