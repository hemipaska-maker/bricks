"""Result models for the apples-to-apples agent runner."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ToolCallRecord(BaseModel):
    """Record of a single tool call made by the agent during a run."""

    name: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    output: Any = None


class AgentResult(BaseModel):
    """Result of a single agent run (with or without Bricks tools).

    Attributes:
        task: The natural language task prompt given to the agent.
        mode: Either ``"no_tools"`` or ``"bricks"``.
        turns: Number of API round-trips in the conversation.
        total_input_tokens: Accumulated input tokens across all turns.
        total_output_tokens: Accumulated output tokens across all turns.
        total_tokens: Sum of input and output tokens.
        tool_calls: Ordered list of tool calls made (bricks mode only).
        final_answer: The agent's final text response.
        code_generated: Python code extracted from the response (no_tools mode).
        blueprint_yaml: Last Blueprint YAML passed to execute_blueprint (bricks mode).
        execution_result: Outputs dict from the last execute_blueprint call (bricks mode).
        duration_seconds: Wall-clock time for the full run.
    """

    task: str
    mode: str  # "no_tools" or "bricks"
    turns: int
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    final_answer: str = ""
    code_generated: str | None = None
    blueprint_yaml: str | None = None
    execution_result: dict[str, Any] | None = None
    duration_seconds: float = 0.0
