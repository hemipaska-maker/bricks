"""API route handlers for the Bricks Playground web server.

All routes live under the ``/playground`` prefix per design.md §6.
"""

from __future__ import annotations

import csv
import io
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]
from fastapi import APIRouter, File, HTTPException, UploadFile

from bricks import __version__ as _bricks_version
from bricks.llm.base import LLMProvider
from bricks.playground.web.schemas import (
    EngineResult,
    RunMetadata,
    RunRequest,
    RunResponse,
    ScenarioDetail,
    ScenarioSummary,
    TokenBreakdown,
    UploadResponse,
)

router = APIRouter(prefix="/playground")

_PRESETS_DIR = Path(__file__).parent / "presets"
_UPLOAD_MAX_BYTES = 5 * 1024 * 1024  # 5 MB


def _build_provider(provider: str, model: str, api_key: str | None) -> LLMProvider:
    """Return an LLMProvider for the given ``provider`` / ``model`` pair.

    All four providers from design.md §7 are implemented here. API keys
    live only in the request body (BYOK) and are never read from the
    environment.

    Args:
        provider: One of ``anthropic`` / ``openai`` / ``claude_code`` / ``ollama``.
        model: Provider-specific model identifier.
        api_key: BYOK key (required for anthropic / openai, ignored for
            ``claude_code`` and ``ollama``).

    Returns:
        An ``LLMProvider`` instance.

    Raises:
        HTTPException: 400 if BYOK is required but missing.
    """
    if provider == "claude_code":
        from bricks.providers.claudecode import ClaudeCodeProvider

        return ClaudeCodeProvider(model=model or None)

    if provider == "ollama":
        from bricks.providers.ollama import OllamaProvider

        return OllamaProvider(model=model)

    if provider in {"anthropic", "openai"} and not api_key:
        raise HTTPException(status_code=400, detail=f"{provider} requires an api_key in the request body (BYOK)")

    if provider == "anthropic":
        from bricks.providers.anthropic import AnthropicProvider

        assert api_key is not None  # narrowed by the BYOK check above
        return AnthropicProvider(model=model, api_key=api_key)

    if provider == "openai":
        from bricks.providers.openai import OpenAIProvider

        assert api_key is not None
        return OpenAIProvider(model=model, api_key=api_key)

    raise HTTPException(
        status_code=400,
        detail=f"Unknown provider {provider!r}",
    )


def _preset_path(scenario_id: str) -> Path | None:
    """Resolve ``scenario_id`` to a YAML file inside ``presets/``.

    Accepts both ``crm-pipeline`` (dashes) and ``crm_pipeline`` (underscores).
    Returns ``None`` if no match exists.
    """
    for sep in (scenario_id, scenario_id.replace("-", "_"), scenario_id.replace("_", "-")):
        candidate = _PRESETS_DIR / f"{sep}.yaml"
        if candidate.is_file():
            return candidate
    return None


def _load_preset_dict(path: Path) -> dict[str, Any]:
    """Parse a preset YAML file into a dict; raise 500 on malformed YAML."""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise HTTPException(status_code=500, detail=f"Malformed preset {path.name!r}: {exc}") from exc
    if not isinstance(data, dict):
        raise HTTPException(status_code=500, detail=f"Preset {path.name!r} did not parse to a mapping")
    return data


# ── GET /playground/scenarios ────────────────────────────────────────────────


@router.get("/scenarios", response_model=list[ScenarioSummary])
async def list_scenarios() -> list[ScenarioSummary]:
    """Return the list of available preset scenarios."""
    out: list[ScenarioSummary] = []
    if not _PRESETS_DIR.is_dir():
        return out
    for path in sorted(_PRESETS_DIR.glob("*.yaml")):
        data = _load_preset_dict(path)
        out.append(
            ScenarioSummary(
                id=path.stem.replace("_", "-"),
                name=str(data.get("name", path.stem)),
                description=str(data.get("description", "")),
            )
        )
    return out


# ── GET /playground/scenarios/{id} ───────────────────────────────────────────


@router.get("/scenarios/{scenario_id}", response_model=ScenarioDetail)
async def get_scenario(scenario_id: str) -> ScenarioDetail:
    """Return the full body of a preset scenario."""
    path = _preset_path(scenario_id)
    if path is None:
        raise HTTPException(status_code=404, detail=f"No scenario with id {scenario_id!r}")
    data = _load_preset_dict(path)

    # Resolve the data source: inline `data`, else `dataset_id` lookup via
    # DatasetLoader (existing helper), else raise 500 if none.
    body: Any = data.get("data")
    dataset_id = data.get("dataset_id")
    if body is None and dataset_id:
        from bricks.playground.web.datasets import DatasetLoader

        loader = DatasetLoader()
        matching = next((ds for ds in loader.list_datasets() if ds.get("id") == dataset_id), None)
        if matching is None:
            raise HTTPException(status_code=500, detail=f"Dataset {dataset_id!r} referenced by preset not found")
        # DatasetLoader gives us a full_data JSON string; parse to a value.
        full = matching.get("full_data")
        if isinstance(full, str):
            try:
                body = json.loads(full)
            except json.JSONDecodeError:
                body = full
        else:
            body = full

    return ScenarioDetail(
        id=scenario_id,
        name=str(data.get("name", scenario_id)),
        description=str(data.get("description", "")),
        task=str(data.get("task_text", "")),
        data=body,
        expected_output=data.get("expected_outputs"),
        required_bricks=data.get("required_bricks"),
    )


# ── POST /playground/upload ──────────────────────────────────────────────────


@router.post("/upload", response_model=UploadResponse)
async def upload(file: UploadFile = File(...)) -> UploadResponse:  # noqa: B008
    """Accept a CSV or JSON upload; return parsed contents.

    Rejects payloads larger than ``_UPLOAD_MAX_BYTES`` (5 MB).
    """
    raw = await file.read()
    if len(raw) > _UPLOAD_MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds {_UPLOAD_MAX_BYTES // (1024 * 1024)} MB limit ({len(raw)} bytes)",
        )

    filename = file.filename or "upload"
    suffix = Path(filename).suffix.lower()

    data: Any
    row_count: int | None = None

    if suffix == ".csv" or (file.content_type or "").endswith("csv"):
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=400, detail=f"CSV must be UTF-8: {exc}") from exc
        reader = csv.DictReader(io.StringIO(text))
        rows = list(reader)
        data = rows
        row_count = len(rows)
    else:
        # Default to JSON.
        try:
            text = raw.decode("utf-8")
            data = json.loads(text)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=400, detail=f"Could not parse JSON: {exc}") from exc
        if isinstance(data, list):
            row_count = len(data)

    return UploadResponse(
        data=data,
        filename=filename,
        size_bytes=len(raw),
        row_count=row_count,
    )


# ── POST /playground/run ─────────────────────────────────────────────────────


def _checks_for(outputs: dict[str, Any], expected: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Build per-key correctness checks; empty list if no expected output."""
    if expected is None:
        return []
    got = outputs or {}
    return [{"key": k, "expected": v, "got": got.get(k), "pass": got.get(k) == v} for k, v in expected.items()]


def _engine_result(result: Any, duration_ms: int, expected: dict[str, Any] | None, *, is_raw: bool) -> EngineResult:
    """Shape a showcase engine result into an :class:`EngineResult`."""
    outputs = result.outputs or {}
    return EngineResult(
        blueprint_yaml=None if is_raw else (result.raw_response or None),
        outputs=outputs,
        response=result.raw_response if is_raw else None,
        tokens=TokenBreakdown(
            **{
                "in": result.tokens_in,
                "out": result.tokens_out,
                "total": result.tokens_in + result.tokens_out,
            }
        ),
        duration_ms=duration_ms,
        cost_usd=None,
        checks=_checks_for(outputs, expected),
    )


@router.post("/run", response_model=RunResponse, response_model_exclude_none=True)
async def run_playground(req: RunRequest) -> RunResponse:
    """Run BricksEngine on the task and return structured results.

    When ``compare`` is ``True``, also runs ``RawLLMEngine`` and includes
    the ``raw_llm`` branch in the response. When ``False`` (default),
    ``RawLLMEngine`` is **not** instantiated or called — the response
    omits the ``raw_llm`` key entirely.
    """
    from bricks.playground.showcase.engine import BricksEngine, RawLLMEngine

    provider = _build_provider(req.provider, req.model, req.api_key)

    raw_data = req.data if isinstance(req.data, str) else json.dumps(req.data)
    fenced = raw_data if raw_data.strip().startswith("```") else f"```json\n{raw_data}\n```"

    t0 = time.monotonic()
    bricks_raw = BricksEngine(provider=provider).solve(req.task, fenced)
    bricks_ms = int((time.monotonic() - t0) * 1000)

    raw_llm_result: EngineResult | None = None
    if req.compare:
        t_raw = time.monotonic()
        raw_raw = RawLLMEngine(provider=provider).solve(req.task, fenced)
        raw_ms = int((time.monotonic() - t_raw) * 1000)
        raw_llm_result = _engine_result(raw_raw, raw_ms, req.expected_output, is_raw=True)

    metadata = RunMetadata(
        model=bricks_raw.model or req.model,
        provider=req.provider,
        version=_bricks_version,
        timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    )

    return RunResponse(
        bricks=_engine_result(bricks_raw, bricks_ms, req.expected_output, is_raw=False),
        raw_llm=raw_llm_result,
        run_metadata=metadata,
    )
