"""Pydantic models for Brick metadata and YAML sequence definitions."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class BrickMeta(BaseModel):
    """Metadata attached to a registered Brick."""

    name: str
    tags: list[str] = Field(default_factory=list)
    destructive: bool = False
    idempotent: bool = True
    description: str = ""


class StepDefinition(BaseModel):
    """A single step within a sequence definition (parsed from YAML)."""

    name: str
    brick: str
    params: dict[str, Any] = Field(default_factory=dict)
    save_as: str | None = None


class SequenceDefinition(BaseModel):
    """A complete sequence definition (parsed from YAML).

    Represents the top-level structure of a sequence YAML file.
    """

    name: str
    description: str = ""
    inputs: dict[str, str] = Field(default_factory=dict)
    steps: list[StepDefinition] = Field(default_factory=list)
    outputs_map: dict[str, str] = Field(default_factory=dict)
