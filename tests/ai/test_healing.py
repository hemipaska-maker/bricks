"""Tests for the ``HealerChain`` orchestrator and related dataclasses.

Concrete healer tiers (10/15/20/30/40) have their own test modules; this
file only exercises the chain mechanics: tier ordering, max_attempts cap,
the BrickExecutionError-only retry contract, and the trace produced in
:class:`ChainResult`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from bricks.ai.healing import (
    ChainResult,
    HealAttempt,
    HealContext,
    HealerChain,
    HealResult,
)
from bricks.core.exceptions import BrickExecutionError

# --- test doubles -----------------------------------------------------------


@dataclass
class _StubFlow:
    """Stand-in for a FlowDefinition — the chain only treats it as an opaque
    handle the executor receives. Carries an identifier so tests can assert
    which flow reached the executor."""

    label: str


@dataclass
class _FakeHealer:
    """Configurable healer for chain-mechanics tests.

    Records every ``can_heal`` / ``heal`` invocation so assertions can
    inspect the sequence.
    """

    tier: int
    name: str
    produces_dsl: str = ""
    produces_flow: _StubFlow | None = None
    accept: bool = True
    tokens_in: int = 0
    tokens_out: int = 0
    heal_calls: list[HealContext] = field(default_factory=list)
    can_heal_calls: list[HealContext] = field(default_factory=list)

    def can_heal(self, ctx: HealContext) -> bool:
        self.can_heal_calls.append(ctx)
        return self.accept

    def heal(self, ctx: HealContext) -> HealResult:
        self.heal_calls.append(ctx)
        return HealResult(
            new_dsl=self.produces_dsl,
            new_flow=self.produces_flow,
            tokens_in=self.tokens_in,
            tokens_out=self.tokens_out,
        )


def _make_ctx(error_message: str = "simulated failure") -> HealContext:
    """Build a minimal HealContext. The failed_flow is a stub — the chain
    never introspects it in scaffolding-level tests."""
    return HealContext(
        task="pretend task",
        failed_flow=_StubFlow(label="original"),  # type: ignore[arg-type]
        failed_dsl="@flow\ndef pretend(): return 1\n",
        error=BrickExecutionError("brick_x", "step_1_brick_x", RuntimeError(error_message)),
        attempt=0,
        prior_attempts=[],
    )


def _ok_executor(outputs: dict[str, Any]):
    """Return an executor that always returns *outputs*."""

    def _run(_: Any) -> dict[str, Any]:
        return outputs

    return _run


def _failing_executor(message: str = "still broken"):
    """Return an executor that always raises BrickExecutionError."""

    def _run(_: Any) -> dict[str, Any]:
        raise BrickExecutionError("brick_x", "step_1_brick_x", RuntimeError(message))

    return _run


def _noop_parser(_: str) -> _StubFlow:
    """Return a stub flow. The chain only needs the executor to accept it."""
    return _StubFlow(label="parsed")


# --- tests ------------------------------------------------------------------


class TestHealerChainOrdering:
    """Chain must sort healers by tier ascending and pick the first match."""

    def test_healers_sorted_ascending_on_construction(self) -> None:
        high = _FakeHealer(tier=40, name="t40")
        mid = _FakeHealer(tier=20, name="t20")
        low = _FakeHealer(tier=10, name="t10")
        chain = HealerChain(healers=[high, low, mid])
        assert [h.tier for h in chain.healers] == [10, 20, 40]

    def test_lowest_tier_with_can_heal_true_wins(self) -> None:
        declines = _FakeHealer(tier=10, name="t10", accept=False)
        winner = _FakeHealer(tier=20, name="t20", produces_dsl="@flow\ndef x():\n    return 1\n")
        loser_later = _FakeHealer(tier=30, name="t30", produces_dsl="should_not_run")
        chain = HealerChain(healers=[loser_later, declines, winner], max_attempts=1)

        result = chain.heal(
            _make_ctx(),
            executor=_ok_executor({"result": 42}),
            parser=_noop_parser,
        )

        assert result.success is True
        assert declines.heal_calls == [], "declining healer must not be invoked"
        assert len(winner.heal_calls) == 1, "tier 20 should run"
        assert loser_later.heal_calls == [], "tier 30 must not run after tier 20 succeeds"


class TestMaxAttempts:
    """Chain must stop after max_attempts iterations even if healers keep
    proposing flows."""

    def test_caps_iterations(self) -> None:
        always_fails = _FakeHealer(tier=20, name="t20", produces_dsl="@flow\ndef x():\n    return 1\n")
        chain = HealerChain(healers=[always_fails], max_attempts=2)

        result = chain.heal(
            _make_ctx(),
            executor=_failing_executor("still broken"),
            parser=_noop_parser,
        )

        assert result.success is False
        assert len(result.attempts) == 2
        assert all(a.exec_succeeded is False for a in result.attempts)
        assert result.final_error, "final_error must describe the last failure"

    def test_single_attempt_default(self) -> None:
        # max_attempts=2 is the class default — exercise that without
        # overriding it.
        healer = _FakeHealer(tier=20, name="t20", produces_dsl="@flow\ndef x():\n    return 1\n")
        chain = HealerChain(healers=[healer])
        assert chain._max_attempts == 2


class TestHealerDeclining:
    """When no healer's can_heal returns True, chain stops immediately
    with an empty-attempts ChainResult."""

    def test_all_decline_short_circuits(self) -> None:
        mute = _FakeHealer(tier=10, name="t10", accept=False)
        chain = HealerChain(healers=[mute], max_attempts=3)

        result = chain.heal(
            _make_ctx("original error"),
            executor=_ok_executor({"should": "not run"}),
            parser=_noop_parser,
        )

        assert result.success is False
        assert result.attempts == []
        assert "original error" in result.final_error


class TestProducedNothing:
    """A healer that returns HealResult with no DSL and no flow must be
    recorded as an attempt but not trigger an executor call."""

    def test_empty_result_still_records_attempt(self) -> None:
        shrugs = _FakeHealer(tier=10, name="t10")  # produces_dsl="" by default
        chain = HealerChain(healers=[shrugs], max_attempts=1)

        executor_calls: list[Any] = []

        def _exec(flow: Any) -> dict[str, Any]:
            executor_calls.append(flow)
            return {}

        result = chain.heal(_make_ctx(), executor=_exec, parser=_noop_parser)

        assert executor_calls == [], "executor must not run when healer produced nothing"
        assert len(result.attempts) == 1
        assert result.attempts[0].produced_flow is False
        assert result.attempts[0].exec_succeeded is None


class TestErrorPassthrough:
    """Non-BrickExecutionError exceptions from the executor must propagate
    unchanged — we do not want to mask framework bugs."""

    def test_non_brick_exception_propagates(self) -> None:
        healer = _FakeHealer(tier=20, name="t20", produces_dsl="@flow\ndef x():\n    return 1\n")
        chain = HealerChain(healers=[healer], max_attempts=3)

        def _explode(_: Any) -> dict[str, Any]:
            raise RuntimeError("framework bug — do not retry")

        with pytest.raises(RuntimeError, match="framework bug"):
            chain.heal(_make_ctx(), executor=_explode, parser=_noop_parser)


class TestSuccessfulHealTrace:
    """ChainResult.attempts must record an exec_succeeded=True entry for
    the winning attempt and carry tokens through."""

    def test_success_carries_tokens_and_outputs(self) -> None:
        healer = _FakeHealer(
            tier=20,
            name="t20",
            produces_dsl="@flow\ndef ok():\n    return 1\n",
            tokens_in=100,
            tokens_out=40,
        )
        chain = HealerChain(healers=[healer], max_attempts=2)

        result = chain.heal(
            _make_ctx(),
            executor=_ok_executor({"answer": 42}),
            parser=_noop_parser,
        )

        assert result.success is True
        assert result.outputs == {"answer": 42}
        assert result.total_tokens_in == 100
        assert result.total_tokens_out == 40
        assert len(result.attempts) == 1
        assert result.attempts[0].exec_succeeded is True
        assert result.attempts[0].healer_name == "t20"

    def test_healer_returning_prebuilt_flow_skips_parser(self) -> None:
        prebuilt = _StubFlow(label="prebuilt")
        healer = _FakeHealer(tier=20, name="t20", produces_flow=prebuilt)
        chain = HealerChain(healers=[healer], max_attempts=1)

        executed: list[Any] = []

        def _exec(flow: Any) -> dict[str, Any]:
            executed.append(flow)
            return {}

        parser_calls: list[str] = []

        def _parser(dsl: str) -> _StubFlow:
            parser_calls.append(dsl)
            return _StubFlow(label="fallback-parsed")

        chain.heal(_make_ctx(), executor=_exec, parser=_parser)

        assert executed == [prebuilt], "prebuilt flow must reach executor verbatim"
        assert parser_calls == [], "parser must not be called when new_flow is already set"


def test_heal_attempt_defaults() -> None:
    """Smoke test the HealAttempt dataclass defaults so later refactors do
    not silently break assumptions used by other tests."""
    att = HealAttempt(healer_name="x", tier=10, produced_flow=False, exec_succeeded=None)
    assert att.error_after == ""
    assert att.tokens_in == 0
    assert att.tokens_out == 0


def test_chain_result_defaults() -> None:
    """Smoke test the ChainResult dataclass defaults."""
    result = ChainResult(success=False)
    assert result.outputs is None
    assert result.final_flow is None
    assert result.final_dsl == ""
    assert result.attempts == []
    assert result.total_tokens_in == 0
    assert result.total_tokens_out == 0
