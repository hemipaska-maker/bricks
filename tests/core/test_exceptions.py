"""Tests for bricks.core.exceptions."""

from __future__ import annotations

import pytest

from bricks.core.exceptions import (
    BrickError,
    BrickExecutionError,
    BrickNotFoundError,
    ConfigError,
    DuplicateBrickError,
    SequenceValidationError,
    VariableResolutionError,
    YamlLoadError,
)


class TestBrickError:
    def test_is_exception(self) -> None:
        err = BrickError("base error")
        assert isinstance(err, Exception)

    def test_message(self) -> None:
        err = BrickError("something went wrong")
        assert "something went wrong" in str(err)


class TestDuplicateBrickError:
    def test_inherits_brick_error(self) -> None:
        err = DuplicateBrickError("my_brick")
        assert isinstance(err, BrickError)

    def test_message_contains_name(self) -> None:
        err = DuplicateBrickError("my_brick")
        assert "my_brick" in str(err)

    def test_name_attribute(self) -> None:
        err = DuplicateBrickError("my_brick")
        assert err.name == "my_brick"

    def test_different_name(self) -> None:
        err = DuplicateBrickError("other_brick")
        assert err.name == "other_brick"
        assert "other_brick" in str(err)


class TestBrickNotFoundError:
    def test_inherits_brick_error(self) -> None:
        err = BrickNotFoundError("missing_brick")
        assert isinstance(err, BrickError)

    def test_message_contains_name(self) -> None:
        err = BrickNotFoundError("missing_brick")
        assert "missing_brick" in str(err)

    def test_name_attribute(self) -> None:
        err = BrickNotFoundError("missing_brick")
        assert err.name == "missing_brick"

    def test_is_catchable_as_brick_error(self) -> None:
        with pytest.raises(BrickError):
            raise BrickNotFoundError("some_brick")


class TestSequenceValidationError:
    def test_inherits_brick_error(self) -> None:
        err = SequenceValidationError("invalid")
        assert isinstance(err, BrickError)

    def test_message(self) -> None:
        err = SequenceValidationError("bad sequence")
        assert "bad sequence" in str(err)

    def test_errors_list(self) -> None:
        err = SequenceValidationError("2 errors", errors=["err1", "err2"])
        assert err.errors == ["err1", "err2"]

    def test_errors_default_empty_list(self) -> None:
        # Implementation returns [] (not None) when no errors list is provided
        err = SequenceValidationError("no errors list")
        assert err.errors == []

    def test_errors_none_becomes_empty_list(self) -> None:
        err = SequenceValidationError("msg", errors=None)
        assert err.errors == []

    def test_multiple_errors_preserved(self) -> None:
        errors = ["error 1", "error 2", "error 3"]
        err = SequenceValidationError("3 errors", errors=errors)
        assert len(err.errors) == 3
        assert "error 1" in err.errors


class TestVariableResolutionError:
    def test_inherits_brick_error(self) -> None:
        err = VariableResolutionError("${unknown}")
        assert isinstance(err, BrickError)

    def test_message_contains_reference(self) -> None:
        err = VariableResolutionError("${inputs.missing}")
        assert "inputs.missing" in str(err)

    def test_reference_attribute(self) -> None:
        err = VariableResolutionError("${my_var}")
        assert err.reference == "${my_var}"

    def test_is_catchable_as_brick_error(self) -> None:
        with pytest.raises(BrickError):
            raise VariableResolutionError("${x}")


class TestBrickExecutionError:
    def test_inherits_brick_error(self) -> None:
        err = BrickExecutionError("my_brick", "step_1", ValueError("oops"))
        assert isinstance(err, BrickError)

    def test_message_contains_brick_and_step(self) -> None:
        err = BrickExecutionError("my_brick", "step_1", ValueError("oops"))
        msg = str(err)
        assert "my_brick" in msg
        assert "step_1" in msg

    def test_cause_attribute(self) -> None:
        cause = ValueError("root cause")
        err = BrickExecutionError("b", "s", cause)
        assert err.cause is cause

    def test_brick_name_attribute(self) -> None:
        err = BrickExecutionError("my_brick", "step_1", RuntimeError())
        assert err.brick_name == "my_brick"

    def test_step_name_attribute(self) -> None:
        err = BrickExecutionError("my_brick", "step_1", RuntimeError())
        assert err.step_name == "step_1"

    def test_cause_preserved_exactly(self) -> None:
        original = RuntimeError("the original cause")
        err = BrickExecutionError("b", "s", original)
        assert err.cause is original
        assert str(original) in str(err)


class TestYamlLoadError:
    def test_inherits_brick_error(self) -> None:
        err = YamlLoadError("/path/to/file.yaml", ValueError("bad yaml"))
        assert isinstance(err, BrickError)

    def test_message_contains_path(self) -> None:
        err = YamlLoadError("/path/to/file.yaml", ValueError("bad yaml"))
        assert "/path/to/file.yaml" in str(err)

    def test_path_attribute(self) -> None:
        err = YamlLoadError("/some/path.yaml", ValueError("x"))
        assert err.path == "/some/path.yaml"

    def test_cause_attribute(self) -> None:
        cause = ValueError("root cause")
        err = YamlLoadError("/f.yaml", cause)
        assert err.cause is cause

    def test_string_source(self) -> None:
        err = YamlLoadError("<string>", ValueError("parse error"))
        assert "<string>" in str(err)
        assert err.path == "<string>"


class TestConfigError:
    def test_inherits_brick_error(self) -> None:
        err = ConfigError("/path/config.yaml", ValueError("bad"))
        assert isinstance(err, BrickError)

    def test_message_contains_path(self) -> None:
        err = ConfigError("/path/config.yaml", ValueError("bad"))
        assert "/path/config.yaml" in str(err)

    def test_path_attribute(self) -> None:
        err = ConfigError("/cfg.yaml", ValueError("x"))
        assert err.path == "/cfg.yaml"

    def test_cause_attribute(self) -> None:
        cause = ValueError("config parse error")
        err = ConfigError("/cfg.yaml", cause)
        assert err.cause is cause

    def test_is_catchable_as_brick_error(self) -> None:
        with pytest.raises(BrickError):
            raise ConfigError("/cfg.yaml", ValueError("oops"))
