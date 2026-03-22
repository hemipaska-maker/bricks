"""Scenario D: apples-to-apples determinism (5 runs with identical inputs)."""

from __future__ import annotations

from typing import Any

from benchmark.constants import DETERMINISM_RUNS
from benchmark.mcp.agent_result import AgentResult
from benchmark.mcp.agent_runner import AgentRunner, OnTurnCallback
from bricks.core import BrickRegistry


def run_d(
    runner: AgentRunner,
    task_text: str,
    registry: BrickRegistry,
    on_turn: OnTurnCallback = None,
) -> dict[str, Any]:
    """Run a task multiple times with identical inputs in both modes.

    No_tools: compare generated code across runs — shows variability.
    Bricks: compare Blueprint YAML across runs — should be identical.

    Args:
        runner: Configured AgentRunner instance.
        task_text: Task description.
        registry: BrickRegistry for the bricks mode.
        on_turn: Optional per-turn callback for logging.

    Returns:
        Dict with per-mode uniqueness metrics and per-run token counts.
    """
    no_tools_results: list[AgentResult] = []
    bricks_results: list[AgentResult] = []

    for _ in range(DETERMINISM_RUNS):
        no_tools_results.append(runner.run_without_tools(task_text, on_turn=on_turn))
        bricks_results.append(runner.run_with_bricks(task_text, registry, on_turn=on_turn))

    codes = [r.code_generated or "" for r in no_tools_results]
    unique_codes = len(set(codes))

    yamls = [r.blueprint_yaml or "" for r in bricks_results]
    unique_yamls = len(set(yamls))

    return {
        "runs": DETERMINISM_RUNS,
        "no_tools": {
            "unique_outputs": unique_codes,
            "all_identical": unique_codes == 1,
        },
        "bricks": {
            "unique_blueprints": unique_yamls,
            "all_identical": unique_yamls == 1,
        },
        "no_tools_results": [{"run": i + 1, "total_tokens": r.total_tokens} for i, r in enumerate(no_tools_results)],
        "bricks_results": [
            {"run": i + 1, "total_tokens": r.total_tokens, "turns": r.turns} for i, r in enumerate(bricks_results)
        ],
    }
