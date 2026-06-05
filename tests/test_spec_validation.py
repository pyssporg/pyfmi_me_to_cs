"""Tests for spec parsing and validation."""
from __future__ import annotations

import os
import tempfile
import textwrap

import pytest

from cs_fmu_packager.errors import SpecValidationError
from cs_fmu_packager.spec import parse_spec


def _write_spec(content: str) -> str:
    """Write a TOML spec to a temp file and return the path."""
    fd, path = tempfile.mkstemp(suffix=".toml")
    with os.fdopen(fd, "w") as f:
        f.write(textwrap.dedent(content))
    return path


def _valid_spec() -> str:
    return """
[metadata]
identifier = "test_fmu"
description = "Test FMU"
author = "test"
version = "0.1.0"

[fmus]
source = { path = "/dev/null/fake.fmu", fmi_version = "2.0", kind = "ModelExchange" }
target = { path = "/dev/null/fake2.fmu", fmi_version = "2.0", kind = "ModelExchange" }

[[connections]]
source = "source.x"
target = "target.y"

[[variables]]
name = "input1"
type = "Real"
causality = "input"
target = "source.u"

[[variables]]
name = "output1"
type = "Real"
causality = "output"
source = "target.result"

[solver]
type = "fixed_step"
step_size = 0.001
communication_step = 0.01

[wrapper]
communication_step = 0.01
"""


class TestSpecParsing:
    """VR-004: Invalid variable reference → error"""
    def test_valid_spec_parses(self):
        path = _write_spec(_valid_spec())
        spec = parse_spec(path)
        assert spec.metadata["identifier"] == "test_fmu"
        assert len(spec.fmus) == 2
        assert len(spec.connections) == 1
        assert len(spec.variables) == 2
        assert spec.solver.step_size == 0.001
        assert spec.wrapper.communication_step == 0.01

    def test_missing_fmus_section(self):
        content = """
[[connections]]
[[variables]]
[solver]
type = "fixed_step"
step_size = 0.001
communication_step = 0.001
[wrapper]
communication_step = 0.001
"""
        path = _write_spec(content)
        with pytest.raises(SpecValidationError) as exc:
            parse_spec(path)
        assert "Missing required section" in str(exc.value)

    def test_missing_connections_section(self):
        content = """
[fmus]
a = { path = "/dev/null/a.fmu" }
[[variables]]
name = "x"
type = "Real"
[solver]
type = "fixed_step"
step_size = 0.001
communication_step = 0.001
[wrapper]
communication_step = 0.001
"""
        path = _write_spec(content)
        with pytest.raises(SpecValidationError) as exc:
            parse_spec(path)
        assert "Missing required section" in str(exc.value)

    def test_invalid_fmi_version(self):
        """VR-004: Invalid FMU metadata → error"""
        content = """
[fmus]
source = { path = "/dev/null/fake.fmu", fmi_version = "1.0", kind = "ModelExchange" }
[[connections]]
source = "source.x"
target = "source.y"
[[variables]]
name = "x"
type = "Real"
causality = "input"
target = "source.u"
[solver]
type = "fixed_step"
step_size = 0.001
communication_step = 0.01
[wrapper]
communication_step = 0.01
"""
        path = _write_spec(content)
        with pytest.raises(SpecValidationError) as exc:
            parse_spec(path)
        assert "fmi_version" in str(exc.value)

    def test_invalid_variable_type(self):
        """VR-004: Invalid variable type → error"""
        content = """
[fmus]
a = { path = "/dev/null/a.fmu" }
[[connections]]
source = "a.x"
target = "a.y"
[[variables]]
name = "x"
type = "Integer"
causality = "input"
[solver]
type = "fixed_step"
step_size = 0.001
communication_step = 0.001
[wrapper]
communication_step = 0.001
"""
        path = _write_spec(content)
        with pytest.raises(SpecValidationError) as exc:
            parse_spec(path)
        assert "type must be 'Real'" in str(exc.value)

    def test_duplicate_variable_name(self):
        """VR-005: Duplicate wrapper names → error"""
        content = """
[fmus]
a = { path = "/dev/null/a.fmu" }
[[connections]]
source = "a.x"
target = "a.y"
[[variables]]
name = "dup"
type = "Real"
causality = "input"
[[variables]]
name = "dup"
type = "Real"
causality = "output"
[solver]
type = "fixed_step"
step_size = 0.001
communication_step = 0.001
[wrapper]
communication_step = 0.001
"""
        path = _write_spec(content)
        with pytest.raises(SpecValidationError) as exc:
            parse_spec(path)
        assert "duplicate variable name" in str(exc.value)

    def test_step_size_greater_than_comm_step(self):
        content = """
[fmus]
a = { path = "/dev/null/a.fmu" }
[[connections]]
source = "a.x"
target = "a.y"
[[variables]]
name = "x"
type = "Real"
causality = "input"
[solver]
type = "fixed_step"
step_size = 0.1
communication_step = 0.01
[wrapper]
communication_step = 0.01
"""
        path = _write_spec(content)
        with pytest.raises(SpecValidationError) as exc:
            parse_spec(path)
        assert "step_size" in str(exc.value)

    def test_invalid_fmu_ref_format(self):
        """VR-004: Invalid connection syntax"""
        content = """
[fmus]
a = { path = "/dev/null/a.fmu" }
[[connections]]
source = "invalid_no_dot"
target = "a.y"
[[variables]]
name = "x"
type = "Real"
causality = "input"
[solver]
type = "fixed_step"
step_size = 0.001
communication_step = 0.001
[wrapper]
communication_step = 0.001
"""
        path = _write_spec(content)
        with pytest.raises(SpecValidationError) as exc:
            parse_spec(path)
        assert "invalid format" in str(exc.value)

    def test_unknown_fmu_in_connection(self):
        content = """
[fmus]
a = { path = "/dev/null/a.fmu" }
[[connections]]
source = "nonexistent.x"
target = "a.y"
[[variables]]
name = "x"
type = "Real"
causality = "input"
[solver]
type = "fixed_step"
step_size = 0.001
communication_step = 0.001
[wrapper]
communication_step = 0.001
"""
        path = _write_spec(content)
        with pytest.raises(SpecValidationError) as exc:
            parse_spec(path)
        assert "not defined" in str(exc.value)

    def test_algebraic_loop_config(self):
        content = """
[fmus]
a = { path = "/dev/null/a.fmu" }
[[connections]]
source = "a.x"
target = "a.y"
[[variables]]
name = "x"
type = "Real"
causality = "input"
[solver]
type = "fixed_step"
step_size = 0.001
communication_step = 0.01
algebraic_loop = { max_iterations = 50, tolerance = 1e-8 }
[wrapper]
communication_step = 0.01
"""
        path = _write_spec(content)
        spec = parse_spec(path)
        assert spec.solver.algebraic_loop.max_iterations == 50
        assert spec.solver.algebraic_loop.tolerance == 1e-8

    def test_comm_step_mismatch(self):
        content = """
[fmus]
a = { path = "/dev/null/a.fmu" }
[[connections]]
source = "a.x"
target = "a.y"
[[variables]]
name = "x"
type = "Real"
causality = "input"
[solver]
type = "fixed_step"
step_size = 0.001
communication_step = 0.01
[wrapper]
communication_step = 0.02
"""
        path = _write_spec(content)
        with pytest.raises(SpecValidationError) as exc:
            parse_spec(path)
        assert "communication_step" in str(exc.value) and "equal" in str(exc.value)