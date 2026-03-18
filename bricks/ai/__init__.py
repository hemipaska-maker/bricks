"""Bricks AI composition layer."""

from bricks.ai.composer import BlueprintComposer, ComposerError, ComposeResult

# Deprecated alias — will be removed in v1.0.0
SequenceComposer = BlueprintComposer

__all__ = ["BlueprintComposer", "ComposeResult", "ComposerError", "SequenceComposer"]
