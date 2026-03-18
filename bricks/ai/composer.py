"""AI blueprint composer: single-call YAML generation from natural language.

No tool_use, no multi-turn conversation. The LLM outputs Blueprint YAML as
plain text, which we validate and execute locally.
"""

from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel, Field

from bricks.core.exceptions import BlueprintValidationError, BrickError
from bricks.core.loader import BlueprintLoader
from bricks.core.registry import BrickRegistry
from bricks.core.schema import compact_brick_signatures
from bricks.core.selector import AllBricksSelector, BrickSelector
from bricks.core.utils import strip_code_fence
from bricks.core.validation import BlueprintValidator


class ComposerError(BrickError):
    """Raised when AI composition fails."""

    def __init__(self, message: str, cause: Exception | None = None) -> None:
        """Initialise the error.

        Args:
            message: Human-readable error description.
            cause: The underlying exception, if any.
        """
        super().__init__(message)
        self.cause = cause


class ComposeResult(BaseModel):
    """Result of a Blueprint composition attempt."""

    task: str
    blueprint_yaml: str = ""
    is_valid: bool = False
    validation_errors: list[str] = Field(default_factory=list)
    api_calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    model: str = ""
    duration_seconds: float = 0.0


# System prompt — under 300 tokens without signatures.
_COMPOSE_SYSTEM = """\
You are a Blueprint composer. Given a task and available bricks, output ONLY \
a valid Blueprint YAML block. No explanation, no markdown fences, just raw YAML.

Available bricks:
{signatures}

Blueprint format:
name: blueprint_name
steps:
  - name: step_name
    brick: brick_name
    params:
      key: "${{inputs.param}}"
      key2: "${{prior_step.field}}"
      key3: 42.0
    save_as: result_name
outputs_map:
  output_key: "${{result_name.field}}"

Reference syntax:
- ${{inputs.X}} for task inputs
- ${{save_as_name.field}} for prior step outputs
- Literal values (numbers, strings) allowed

Rules:
- Only use brick names from the list above.
- Every step referenced later needs save_as.
- Step names must be unique snake_case.
- outputs_map values must use ${{inputs.X}} or ${{save_as.field}} syntax.\
"""

_RETRY_PROMPT = """\
The following Blueprint YAML has validation errors:

{yaml}

Errors:
{errors}

Output ONLY the corrected YAML. Nothing else.\
"""

_DEFAULT_MODEL = "claude-haiku-4-5-20251001"
_MAX_TOKENS = 2048
_MAX_API_CALLS = 2


class BlueprintComposer:
    """Composes Blueprint YAML from a natural language task using a single LLM call.

    No tool_use, no multi-turn conversation. The LLM outputs YAML as text,
    which we validate and execute locally.

    If the first attempt fails validation, makes ONE retry with a fresh
    prompt containing the errors. Max 2 API calls total.

    Args:
        api_key: Anthropic API key.
        model: Model ID (default: claude-haiku-4-5-20251001).
        selector: BrickSelector for Stage 1 filtering (default: AllBricksSelector).
    """

    _client: Any

    def __init__(
        self,
        api_key: str,
        model: str = _DEFAULT_MODEL,
        selector: BrickSelector | None = None,
    ) -> None:
        """Initialise the composer.

        Args:
            api_key: Anthropic API key.
            model: The Claude model to use.
            selector: BrickSelector for Stage 1 filtering. Defaults to AllBricksSelector.

        Raises:
            ImportError: If the ``anthropic`` package is not installed.
        """
        try:
            import anthropic  # noqa: PLC0415

            self._client = anthropic.Anthropic(api_key=api_key)
        except ImportError as exc:
            raise ImportError(
                "The 'anthropic' package is required for AI composition. Install with: pip install bricks[ai]"
            ) from exc

        self._model = model
        self._selector = selector or AllBricksSelector()
        self._loader = BlueprintLoader()

    def compose(self, task: str, registry: BrickRegistry) -> ComposeResult:
        """Compose a Blueprint YAML for a task.

        1. Stage 1: selector.select(task, registry) → small pool
        2. Build system prompt with compact brick signatures from pool
        3. Single API call: task → YAML text
        4. Parse YAML → validate → return
        5. If validation fails, ONE retry with error message (fresh call)

        Args:
            task: Natural language task description.
            registry: BrickRegistry with available bricks.

        Returns:
            ComposeResult with blueprint YAML, validation status, and token usage.

        Raises:
            ComposerError: If the API call itself fails (network error, etc.).
        """
        t0 = time.monotonic()
        pool = self._selector.select(task, registry)
        signatures = compact_brick_signatures(pool)
        system = _COMPOSE_SYSTEM.format(signatures=signatures)
        validator = BlueprintValidator(registry=pool)

        total_input = 0
        total_output = 0
        api_calls = 0
        yaml_text = ""
        validation_errors: list[str] = []

        # First call
        yaml_text, in_tok, out_tok = self._call_api(system, task)
        total_input += in_tok
        total_output += out_tok
        api_calls += 1

        is_valid, validation_errors = self._validate_yaml(yaml_text, validator)

        # Retry on failure (fresh call, no history)
        if not is_valid and api_calls < _MAX_API_CALLS:
            retry_prompt = _RETRY_PROMPT.format(
                yaml=yaml_text,
                errors="\n".join(f"- {e}" for e in validation_errors),
            )
            yaml_text, in_tok, out_tok = self._call_api(system, retry_prompt)
            total_input += in_tok
            total_output += out_tok
            api_calls += 1

            is_valid, validation_errors = self._validate_yaml(yaml_text, validator)

        elapsed = time.monotonic() - t0

        return ComposeResult(
            task=task,
            blueprint_yaml=yaml_text,
            is_valid=is_valid,
            validation_errors=validation_errors,
            api_calls=api_calls,
            total_input_tokens=total_input,
            total_output_tokens=total_output,
            total_tokens=total_input + total_output,
            model=self._model,
            duration_seconds=elapsed,
        )

    def _call_api(self, system: str, user_message: str) -> tuple[str, int, int]:
        """Make a single API call and return (yaml_text, input_tokens, output_tokens).

        Args:
            system: System prompt.
            user_message: User message (task or retry prompt).

        Returns:
            Tuple of (extracted YAML text, input tokens, output tokens).

        Raises:
            ComposerError: If the API call fails or returns no text.
        """
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=_MAX_TOKENS,
                system=system,
                messages=[{"role": "user", "content": user_message}],
            )
        except Exception as exc:
            raise ComposerError(f"API call failed: {exc}", cause=exc) from exc

        in_tok: int = response.usage.input_tokens
        out_tok: int = response.usage.output_tokens

        raw_text = self._extract_text(response)
        yaml_text = strip_code_fence(raw_text)
        return yaml_text, in_tok, out_tok

    def _validate_yaml(self, yaml_text: str, validator: BlueprintValidator) -> tuple[bool, list[str]]:
        """Parse and validate a YAML string.

        Args:
            yaml_text: Raw YAML string from the LLM.
            validator: BlueprintValidator to check against.

        Returns:
            Tuple of (is_valid, list_of_error_strings).
        """
        try:
            bp = self._loader.load_string(yaml_text)
            validator.validate(bp)
            return True, []
        except BlueprintValidationError as exc:
            return False, exc.errors
        except Exception as exc:
            return False, [str(exc)]

    def _extract_text(self, response: Any) -> str:
        """Extract text content from an Anthropic response.

        Args:
            response: The raw Anthropic API response object.

        Returns:
            The text content of the first text block.

        Raises:
            ComposerError: If no text block is found.
        """
        for block in response.content:
            if hasattr(block, "text"):
                return str(block.text)
        raise ComposerError("AI response contained no text block")
