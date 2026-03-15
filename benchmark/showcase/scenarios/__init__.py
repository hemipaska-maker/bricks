"""Benchmark scenarios comparing Bricks vs raw code generation."""

from __future__ import annotations

__all__ = ["CODEGEN_SYSTEM"]

CODEGEN_SYSTEM: str = (
    "You are an expert Python programmer. Generate production-ready Python "
    "code using ONLY the provided helper functions. Do not import anything."
)
