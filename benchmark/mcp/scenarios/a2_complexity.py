"""Scenario A2: apples-to-apples complexity curve (3, 6, 12 steps)."""

from __future__ import annotations

from typing import Any

from benchmark.mcp.agent_result import AgentResult
from benchmark.mcp.agent_runner import AgentRunner
from benchmark.mcp.scenarios import TASK_A2_3, TASK_A2_6, TASK_A2_12
from bricks.core import BrickRegistry


def run_a2_3(runner: AgentRunner, registry: BrickRegistry) -> dict[str, Any]:
    """Run A2-3 (room area, 3 steps) in both modes and return comparison dict.

    Args:
        runner: Configured AgentRunner instance.
        registry: BrickRegistry for the bricks mode.

    Returns:
        Comparison dict with ``label``, ``steps``, ``no_tools``, ``bricks``.
    """
    no_tools = runner.run_without_tools(TASK_A2_3)
    bricks = runner.run_with_bricks(TASK_A2_3, registry)
    return _compare("A2-3", 3, no_tools, bricks)


def run_a2_6(runner: AgentRunner, registry: BrickRegistry) -> dict[str, Any]:
    """Run A2-6 (property price, 6 steps) in both modes and return comparison dict.

    Args:
        runner: Configured AgentRunner instance.
        registry: BrickRegistry for the bricks mode.

    Returns:
        Comparison dict with ``label``, ``steps``, ``no_tools``, ``bricks``.
    """
    no_tools = runner.run_without_tools(TASK_A2_6)
    bricks = runner.run_with_bricks(TASK_A2_6, registry)
    return _compare("A2-6", 6, no_tools, bricks)


def run_a2_12(runner: AgentRunner, registry: BrickRegistry) -> dict[str, Any]:
    """Run A2-12 (full valuation, 12 steps) in both modes and return comparison dict.

    Args:
        runner: Configured AgentRunner instance.
        registry: BrickRegistry for the bricks mode.

    Returns:
        Comparison dict with ``label``, ``steps``, ``no_tools``, ``bricks``.
    """
    no_tools = runner.run_without_tools(TASK_A2_12)
    bricks = runner.run_with_bricks(TASK_A2_12, registry)
    return _compare("A2-12", 12, no_tools, bricks)


def _compare(
    label: str,
    steps: int,
    no_tools: AgentResult,
    bricks: AgentResult,
) -> dict[str, Any]:
    """Build a comparison dict from two AgentResult instances.

    Args:
        label: Human-readable sub-scenario label (e.g. ``"A2-3"``).
        steps: Number of Blueprint steps in this sub-scenario.
        no_tools: Result from the no-tools run.
        bricks: Result from the Bricks-tools run.

    Returns:
        Dict with label, steps, and nested no_tools / bricks summaries.
    """
    return {
        "label": label,
        "steps": steps,
        "no_tools": {
            "turns": no_tools.turns,
            "total_tokens": no_tools.total_tokens,
            "code_lines": len((no_tools.code_generated or "").splitlines()),
        },
        "bricks": {
            "turns": bricks.turns,
            "total_tokens": bricks.total_tokens,
            "tool_calls": len(bricks.tool_calls),
        },
    }
