"""Tests for bricks.core.loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from bricks.core.exceptions import YamlLoadError
from bricks.core.loader import SequenceLoader


class TestSequenceLoaderFromString:
    def test_load_minimal_sequence(self) -> None:
        loader = SequenceLoader()
        seq = loader.load_string("name: test_seq\n")
        assert seq.name == "test_seq", f"Expected 'test_seq', got {seq.name!r}"
        assert seq.steps == [], f"Expected [], got {seq.steps!r}"

    def test_load_sequence_with_steps(self) -> None:
        loader = SequenceLoader()
        yaml = "name: my_seq\nsteps:\n  - name: s1\n    brick: do_thing\n"
        seq = loader.load_string(yaml)
        assert len(seq.steps) == 1, f"Expected length 1, got {len(seq.steps)}"
        assert seq.steps[0].name == "s1", f"Expected 's1', got {seq.steps[0].name!r}"
        assert seq.steps[0].brick == "do_thing", f"Expected 'do_thing', got {seq.steps[0].brick!r}"

    def test_load_sequence_with_params_and_save_as(self) -> None:
        loader = SequenceLoader()
        yaml = (
            "name: my_seq\n"
            "steps:\n"
            "  - name: s1\n"
            "    brick: read_voltage\n"
            "    params:\n"
            "      channel: 3\n"
            "    save_as: reading\n"
        )
        seq = loader.load_string(yaml)
        assert seq.steps[0].params == {"channel": 3}, f"Expected {{'channel': 3}}, got {seq.steps[0].params!r}"
        assert seq.steps[0].save_as == "reading", f"Expected 'reading', got {seq.steps[0].save_as!r}"

    def test_load_sequence_with_inputs_and_outputs_map(self) -> None:
        loader = SequenceLoader()
        yaml = (
            "name: my_seq\n"
            "inputs:\n"
            "  voltage: float\n"
            "steps:\n"
            "  - name: s1\n"
            "    brick: read\n"
            "    save_as: result\n"
            "outputs_map:\n"
            '  final: "${result}"\n'
        )
        seq = loader.load_string(yaml)
        assert seq.inputs == {"voltage": "float"}, f"Expected {{'voltage': 'float'}}, got {seq.inputs!r}"
        assert seq.outputs_map == {"final": "${result}"}, "Expected outputs_map mismatch"

    def test_invalid_yaml_syntax_raises(self) -> None:
        loader = SequenceLoader()
        with pytest.raises(YamlLoadError):
            loader.load_string("name: [invalid yaml\n  missing bracket")

    def test_missing_required_name_raises(self) -> None:
        loader = SequenceLoader()
        with pytest.raises(YamlLoadError):
            loader.load_string("description: no name field\n")

    def test_empty_content_raises(self) -> None:
        loader = SequenceLoader()
        with pytest.raises(YamlLoadError):
            loader.load_string("")


class TestSequenceLoaderFromFile:
    def test_load_from_yaml_file(self, tmp_path: Path) -> None:
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text("name: file_test\nsteps:\n  - name: s1\n    brick: x\n")
        loader = SequenceLoader()
        seq = loader.load_file(yaml_file)
        assert seq.name == "file_test", f"Expected 'file_test', got {seq.name!r}"

    def test_file_not_found_raises(self) -> None:
        loader = SequenceLoader()
        with pytest.raises(FileNotFoundError):
            loader.load_file(Path("/nonexistent/file.yaml"))

    def test_empty_file_raises(self, tmp_path: Path) -> None:
        yaml_file = tmp_path / "empty.yaml"
        yaml_file.write_text("")
        loader = SequenceLoader()
        with pytest.raises(YamlLoadError):
            loader.load_file(yaml_file)
