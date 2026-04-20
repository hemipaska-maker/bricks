"""Runtime self-heal for composed blueprints — tiered :class:`Healer` chain.

Composer today retries only on *static* (AST) validation failure. When a
blueprint validates but a brick crashes at execution time, the composer has
no recovery path. This module adds one.

The abstraction is a **chain of healing strategies**, each living at a
distinct ``tier`` (lower runs first). A healer inspects the failure context
and either returns new DSL (``HealResult.new_dsl``) that the chain re-parses
and re-executes, or passes (``new_flow=None``) so the next tier gets a turn.

Tiered layout — healers ship in follow-up commits inside this PR:

    10  ParamNameHealer            deterministic, 0 LLM calls
    15  DictUnwrapHealer           deterministic, 0 LLM calls
    20  LLMRetryHealer             LLM re-prompt with error context
    30  ShapeAwareLLMHealer        LLM re-prompt with observed shapes
    40  FullRecomposeHealer        fresh compose with filtered selector

This commit ships only the scaffolding — the five tiers land in later
commits on the same PR (see #29).

Common substrate: every healer returns DSL **text**. The chain parses the
text back to a ``FlowDefinition`` via ``BlueprintComposer._parse_dsl_response``
and calls the caller-supplied ``executor`` to run it. No direct DAG mutation.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from bricks.core.exceptions import BrickExecutionError

if TYPE_CHECKING:
    from bricks.core.dsl import FlowDefinition
    from bricks.llm.base import LLMProvider


_RUNTIME_RETRY_PROMPT = """\
Original task:
{task}

Your previous DSL compiled but crashed at runtime:

{code}

Runtime error — brick {brick_name!r} at step {step_name!r}:
{cause}

Common fixes:
- If parsing JSON that wraps a list (e.g. {{"customers": [...]}}), use
  step.extract_dict_field(data=parsed.output, field="customers") before filtering.
- reduce_sum takes a LIST of node refs: step.reduce_sum(values=[a, b, c]).
- Brick parameter names must match the signatures exactly.

Output ONLY the corrected Python code. Nothing else.\
"""


_SHAPE_AWARE_RETRY_PROMPT = """\
Original task:
{task}

Your previous DSL compiled but crashed at runtime. Here are the actual
runtime shapes of each step output up to the failure, so you can see
where the data became incompatible:

{shapes}

Failed DSL:

{code}

Runtime error — brick {brick_name!r} at step {step_name!r}:
{cause}

Use the observed shapes to pick the right brick and parameters. If an
earlier step output is a dict that wraps the list you need, insert
extract_dict_field before the consuming step.

Output ONLY the corrected Python code. Nothing else.\
"""


TraceExecutor = Callable[["FlowDefinition"], dict[str, Any]]
"""Variant of :data:`Executor` that returns a mapping of step name to a
short shape description (e.g. ``"list[dict]<len=42>"``). Used by tier 30
(:class:`ShapeAwareLLMHealer`). Raises :class:`BrickExecutionError`
naturally if the blueprint still crashes — the caller is expected to
capture whatever shapes were observed before the raise, not to swallow
the exception itself."""


FreshCompose = Callable[[str, list[str]], "HealResult"]
"""Variant of compose() taking (task, excluded_bricks). Returns a HealResult
with ``new_flow`` set on success (and tokens_in/out populated). Used by
tier 40 (:class:`FullRecomposeHealer`). When compose fails validation, the
callable returns ``HealResult()`` (no flow, no DSL) so the chain records
the tokens spent and moves on."""


def _strip_fences(code: str) -> str:
    """Remove markdown code fences from LLM output, stripping surrounding whitespace."""
    cleaned = code.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [line for line in lines if not line.strip().startswith("```")]
        cleaned = "\n".join(lines)
    return cleaned.strip()


Executor = Callable[["FlowDefinition"], dict[str, Any]]
"""Caller-provided closure that runs a ``FlowDefinition`` and returns its
outputs. Raises :class:`BrickExecutionError` on brick-level failure; other
exceptions propagate through the chain unhandled."""


DSLParser = Callable[[str], "FlowDefinition"]
"""Parses DSL text back to a ``FlowDefinition``. The composer passes
its ``_parse_dsl_response`` method so the chain does not re-implement
AST validation / exec / extraction."""


@dataclass
class HealContext:
    """Inputs a :class:`Healer` sees for a single healing attempt.

    Attributes:
        task: Natural-language task the composer was asked to solve.
        failed_flow: The :class:`FlowDefinition` whose execution just crashed.
        failed_dsl: The DSL text that produced ``failed_flow``. Kept alongside
            the flow so healers that rewrite the DSL (all of them) have the
            source to manipulate.
        error: The brick-level execution error. Only ``BrickExecutionError``
            enters the chain — any other exception propagates unhandled.
        attempt: 0-based index of this healing attempt within the chain's
            ``max_attempts`` budget.
        prior_attempts: Outcome of every previous attempt in this chain
            invocation. Healers consult this to avoid repeating themselves
            (e.g. :class:`ShapeAwareLLMHealer` only fires *after* a tier-20
            attempt has failed).
        registry: The :class:`BrickRegistry` in use. Needed by deterministic
            healers for signature introspection.
    """

    task: str
    failed_flow: FlowDefinition
    failed_dsl: str
    error: BrickExecutionError
    attempt: int
    prior_attempts: list[HealAttempt] = field(default_factory=list)
    registry: Any = None  # BrickRegistry — kept loose to avoid cycles at import time


@dataclass
class HealResult:
    """What a :class:`Healer` returns.

    Attributes:
        new_dsl: Rewritten DSL text. Empty string when ``new_flow is None``.
        new_flow: Pre-parsed flow if the healer already materialised it.
            Most healers return ``new_dsl`` only and let the chain parse;
            :class:`FullRecomposeHealer` returns the flow directly because
            it runs the composer and already has one.
        tokens_in: Input tokens this healer spent (0 for deterministic tiers).
        tokens_out: Output tokens this healer spent.
    """

    new_dsl: str = ""
    new_flow: FlowDefinition | None = None
    tokens_in: int = 0
    tokens_out: int = 0

    @property
    def produced_something(self) -> bool:
        """True iff the healer has a candidate to hand back to the executor."""
        return bool(self.new_dsl) or self.new_flow is not None


@dataclass
class HealAttempt:
    """Trace entry for one iteration of the chain.

    Attributes:
        healer_name: The :attr:`Healer.name` of the strategy that ran.
        tier: The :attr:`Healer.tier` of that strategy.
        produced_flow: Whether the healer returned anything executable.
        exec_succeeded: True if re-executing the produced flow returned
            without raising; False if it raised another ``BrickExecutionError``;
            ``None`` when no flow was produced (nothing to execute).
        error_after: String form of the re-execution error when
            ``exec_succeeded is False``. Empty otherwise.
        tokens_in: Tokens spent by this attempt's healer.
        tokens_out: Tokens spent by this attempt's healer.
    """

    healer_name: str
    tier: int
    produced_flow: bool
    exec_succeeded: bool | None
    error_after: str = ""
    tokens_in: int = 0
    tokens_out: int = 0


@dataclass
class ChainResult:
    """Terminal state of a :meth:`HealerChain.heal` run.

    Attributes:
        success: True iff some attempt produced a flow that executed cleanly.
        outputs: Brick outputs from the successful run. ``None`` on failure.
        final_flow: The FlowDefinition that actually succeeded. ``None`` on
            failure.
        final_dsl: The DSL text of the successful flow.
        final_error: Human-readable final error when ``success is False``.
        attempts: Ordered trace of every healing attempt, including the ones
            that produced nothing — useful for observability and tests.
        total_tokens_in: Sum across attempts; caller folds this into
            ``ComposeResult.total_input_tokens``.
        total_tokens_out: Same, for output tokens.
    """

    success: bool
    outputs: dict[str, Any] | None = None
    final_flow: FlowDefinition | None = None
    final_dsl: str = ""
    final_error: str = ""
    attempts: list[HealAttempt] = field(default_factory=list)
    total_tokens_in: int = 0
    total_tokens_out: int = 0


@runtime_checkable
class Healer(Protocol):
    """Strategy for recovering from a runtime brick failure.

    Attributes:
        tier: Ordering hint — lower tiers run first. Leave gaps between
            concrete values so future healers can slot in.
        name: Stable identifier used in logs and ``HealAttempt.healer_name``.

    Implementations must not depend on which other healers sit earlier or
    later in the chain; the only shared state is :class:`HealContext`.
    """

    tier: int
    name: str

    def can_heal(self, ctx: HealContext) -> bool:
        """Return True iff :meth:`heal` is likely to produce a candidate
        for *ctx*. Returning False lets the chain move to the next tier."""

    def heal(self, ctx: HealContext) -> HealResult:
        """Produce a rewritten DSL (or materialised flow). Return a
        :class:`HealResult` with ``produced_something`` False to decline
        and let the chain continue."""


class HealerChain:
    """Runs a list of :class:`Healer` strategies against one failure.

    On each iteration the chain finds the lowest-tier applicable healer,
    calls it, re-executes the produced flow, and either returns success or
    records a :class:`HealAttempt` and moves to the next iteration. The
    total number of iterations is bounded by ``max_attempts``.

    The chain does **not** retry on non-``BrickExecutionError`` exceptions
    raised by the executor — those escape unchanged so framework bugs
    surface instead of being masked.

    Args:
        healers: The ordered pool of strategies. Sorted internally by
            :attr:`Healer.tier` ascending.
        max_attempts: Hard cap on iterations. Default 2 keeps total LLM
            cost predictable. Set higher for aggressive recovery.
    """

    def __init__(self, healers: list[Healer], max_attempts: int = 2) -> None:
        """Initialise the chain with a pool of healers."""
        self._healers: list[Healer] = sorted(healers, key=lambda h: h.tier)
        self._max_attempts = max_attempts

    @property
    def healers(self) -> list[Healer]:
        """Read-only view of the sorted healer pool — for tests and logs."""
        return list(self._healers)

    def heal(
        self,
        ctx: HealContext,
        executor: Executor,
        parser: DSLParser,
    ) -> ChainResult:
        """Attempt to recover from the failure described by *ctx*.

        Args:
            ctx: Initial failure context. The chain mutates its ``attempt``
                and ``prior_attempts`` fields as it iterates.
            executor: Runs a candidate flow. Must raise
                :class:`BrickExecutionError` on brick failure.
            parser: Turns DSL text into a :class:`FlowDefinition`. Pass the
                composer's ``_parse_dsl_response`` bound method.

        Returns:
            A :class:`ChainResult` reflecting the final state. Never raises
            ``BrickExecutionError`` itself — that is captured in
            ``ChainResult.final_error`` when all attempts exhaust.
        """
        attempts: list[HealAttempt] = []
        tokens_in = 0
        tokens_out = 0

        for attempt_idx in range(self._max_attempts):
            ctx.attempt = attempt_idx
            ctx.prior_attempts = attempts

            healer = self._pick_healer(ctx)
            if healer is None:
                # No tier applies — stop; whatever error is in ctx is final.
                break

            result = healer.heal(ctx)
            tokens_in += result.tokens_in
            tokens_out += result.tokens_out

            if not result.produced_something:
                attempts.append(
                    HealAttempt(
                        healer_name=healer.name,
                        tier=healer.tier,
                        produced_flow=False,
                        exec_succeeded=None,
                        tokens_in=result.tokens_in,
                        tokens_out=result.tokens_out,
                    )
                )
                continue

            new_flow = result.new_flow if result.new_flow is not None else parser(result.new_dsl)

            try:
                outputs = executor(new_flow)
            except BrickExecutionError as exc:
                attempts.append(
                    HealAttempt(
                        healer_name=healer.name,
                        tier=healer.tier,
                        produced_flow=True,
                        exec_succeeded=False,
                        error_after=str(exc),
                        tokens_in=result.tokens_in,
                        tokens_out=result.tokens_out,
                    )
                )
                # Swap in the new failure context for the next iteration.
                ctx = HealContext(
                    task=ctx.task,
                    failed_flow=new_flow,
                    failed_dsl=result.new_dsl or ctx.failed_dsl,
                    error=exc,
                    attempt=attempt_idx,  # re-set on next loop
                    prior_attempts=attempts,
                    registry=ctx.registry,
                )
                continue

            attempts.append(
                HealAttempt(
                    healer_name=healer.name,
                    tier=healer.tier,
                    produced_flow=True,
                    exec_succeeded=True,
                    tokens_in=result.tokens_in,
                    tokens_out=result.tokens_out,
                )
            )
            return ChainResult(
                success=True,
                outputs=outputs,
                final_flow=new_flow,
                final_dsl=result.new_dsl,
                attempts=attempts,
                total_tokens_in=tokens_in,
                total_tokens_out=tokens_out,
            )

        return ChainResult(
            success=False,
            final_error=str(ctx.error),
            attempts=attempts,
            total_tokens_in=tokens_in,
            total_tokens_out=tokens_out,
        )

    def _pick_healer(self, ctx: HealContext) -> Healer | None:
        """Return the lowest-tier healer whose ``can_heal`` accepts *ctx*."""
        for healer in self._healers:
            if healer.can_heal(ctx):
                return healer
        return None


class LLMRetryHealer:
    """Tier 20 — ask the LLM to correct the DSL given the runtime error.

    Accepts any :class:`BrickExecutionError`. Sends a short retry prompt
    (task + failed DSL + brick/step/cause) to the LLM, reusing the same
    system prompt the composer used, so brick signatures remain in scope.

    Args:
        provider: The LLM provider the composer is using. The healer calls
            ``provider.complete(prompt=..., system=...)`` and strips fences.
        system_prompt: The full system prompt composer built for this
            compose call — contains brick signatures and DSL rules. Reused
            verbatim so the LLM has the same context it had on the original
            attempt.
    """

    tier: int = 20
    name: str = "LLMRetryHealer"

    def __init__(self, provider: LLMProvider, system_prompt: str) -> None:
        """Initialise with provider + system prompt."""
        self._provider = provider
        self._system_prompt = system_prompt

    def can_heal(self, ctx: HealContext) -> bool:
        """Always applies — this is the general-purpose tier."""
        del ctx
        return True

    def heal(self, ctx: HealContext) -> HealResult:
        """Send the retry prompt, strip fences, return the corrected DSL."""
        user_prompt = _RUNTIME_RETRY_PROMPT.format(
            task=ctx.task,
            code=ctx.failed_dsl,
            brick_name=ctx.error.brick_name,
            step_name=ctx.error.step_name,
            cause=ctx.error.cause,
        )
        completion = self._provider.complete(prompt=user_prompt, system=self._system_prompt)
        return HealResult(
            new_dsl=_strip_fences(completion.text),
            tokens_in=completion.input_tokens,
            tokens_out=completion.output_tokens,
        )


class ShapeAwareLLMHealer:
    """Tier 30 — LLM retry with observed runtime shapes spliced into the prompt.

    Only fires *after* a tier-20 attempt has already failed — otherwise we
    would pay the cost of a shape trace on the first attempt, when a plain
    LLM retry might have sufficed.

    The healer runs the failed flow through a ``trace_executor`` which is
    expected to capture step outputs even when a later step raises. The
    captured ``{step_name: shape_string}`` dict is included in the retry
    prompt so the LLM can see where data shape diverged from what the
    consuming brick expected.

    Args:
        provider: The LLM provider.
        system_prompt: Same system prompt the composer used.
        trace_executor: Runs the blueprint and returns a ``{step_name:
            shape}`` mapping. If ``None`` the healer's :meth:`can_heal`
            returns False — trace execution is a caller capability and
            not every caller can supply it.
    """

    tier: int = 30
    name: str = "ShapeAwareLLMHealer"

    def __init__(
        self,
        provider: LLMProvider,
        system_prompt: str,
        trace_executor: TraceExecutor | None = None,
    ) -> None:
        """Initialise. trace_executor is optional; without it can_heal is False."""
        self._provider = provider
        self._system_prompt = system_prompt
        self._trace_executor = trace_executor

    def can_heal(self, ctx: HealContext) -> bool:
        """Fire only after a prior tier-20 attempt failed and we have a trace path."""
        if self._trace_executor is None:
            return False
        return any(att.tier == LLMRetryHealer.tier and att.exec_succeeded is False for att in ctx.prior_attempts)

    def heal(self, ctx: HealContext) -> HealResult:
        """Capture shapes via trace_executor, then call the LLM with them."""
        trace_executor = self._trace_executor
        if trace_executor is None:
            # Should be unreachable — can_heal guards this — but we keep a
            # runtime check rather than an assert so production behavior
            # is deterministic instead of silently optimised away under -O.
            return HealResult()
        try:
            shapes = trace_executor(ctx.failed_flow)
        except BrickExecutionError:
            # The flow still crashes under the trace executor — no shapes for
            # the failing step itself, but any earlier shapes captured are
            # better than nothing. trace_executor contract: it records what
            # it saw even on crash. If it genuinely captured nothing, fall
            # back to empty dict.
            shapes = {}
        except Exception:  # tracer is best-effort observability
            shapes = {}

        shapes_block = "\n".join(f"- {name}: {shape}" for name, shape in shapes.items()) or "(no shape info available)"

        user_prompt = _SHAPE_AWARE_RETRY_PROMPT.format(
            task=ctx.task,
            code=ctx.failed_dsl,
            shapes=shapes_block,
            brick_name=ctx.error.brick_name,
            step_name=ctx.error.step_name,
            cause=ctx.error.cause,
        )
        completion = self._provider.complete(prompt=user_prompt, system=self._system_prompt)
        return HealResult(
            new_dsl=_strip_fences(completion.text),
            tokens_in=completion.input_tokens,
            tokens_out=completion.output_tokens,
        )


class FullRecomposeHealer:
    """Tier 40 — recompose from scratch with failed bricks excluded.

    Last-ditch healer. Fires only after three prior attempts failed, so
    the chain has genuine evidence the current blueprint shape is broken.

    Delegates to the caller-supplied ``fresh_compose`` callable, passing
    the list of brick names that appeared in ``BrickExecutionError`` reports
    across the prior attempts. The callable is expected to build a new
    composer with a :class:`~bricks.core.filtering_selector.FilteringSelector`
    wrapping the original selector and excluding those names, then run
    compose. See :class:`BlueprintComposer` for the canonical wiring.

    Args:
        fresh_compose: Takes ``(task, excluded_bricks)`` and returns a
            :class:`HealResult`. On compose-validation failure returns an
            empty result; on success returns ``HealResult(new_flow=...)``.
    """

    tier: int = 40
    name: str = "FullRecomposeHealer"

    def __init__(self, fresh_compose: FreshCompose) -> None:
        """Initialise with a fresh-compose callable."""
        self._fresh_compose = fresh_compose

    def can_heal(self, ctx: HealContext) -> bool:
        """Only fire after we have real evidence the blueprint shape is wrong."""
        return len(ctx.prior_attempts) >= 3

    def heal(self, ctx: HealContext) -> HealResult:
        """Collect brick names from prior errors and kick off a fresh compose."""
        excluded: list[str] = []
        seen: set[str] = set()
        # Gather brick names from every attempt that produced a flow but
        # whose re-execution failed. The order-of-first-seen is preserved
        # so FilteringSelector's exclusion set is deterministic.
        for att in ctx.prior_attempts:
            if att.exec_succeeded is False and att.error_after:
                # Best-effort parse of "Brick 'X' failed at step 'Y': ..."
                marker = "Brick '"
                if marker in att.error_after:
                    start = att.error_after.index(marker) + len(marker)
                    end = att.error_after.index("'", start)
                    brick = att.error_after[start:end]
                    if brick not in seen:
                        seen.add(brick)
                        excluded.append(brick)
        # Always include the current error's brick — it just failed.
        if ctx.error.brick_name not in seen:
            excluded.append(ctx.error.brick_name)

        return self._fresh_compose(ctx.task, excluded)
