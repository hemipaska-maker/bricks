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
