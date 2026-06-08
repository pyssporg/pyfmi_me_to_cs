"""Tests for spec parsing and validation."""
from __future__ import annotations

import pytest

from cs_fmu_packager.errors import SpecValidationError
from cs_fmu_packager.spec import parse_spec


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
    def test_valid_spec_parses(self, spec_file):
        path = spec_file(_valid_spec())
        spec = parse_spec(path)
        assert spec.metadata["identifier"] == "test_fmu"
        assert len(spec.fmus) == 2
        assert len(spec.connections) == 1
        assert len(spec.variables) == 2
        assert spec.solver.step_size == 0.001
        assert spec.wrapper.communication_step == 0.01

    def test_missing_fmus_section(self, spec_file):
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
        path = spec_file(content)
        with pytest.raises(SpecValidationError) as exc:
            parse_spec(path)
        assert "Missing required section" in str(exc.value)

    def test_missing_connections_section(self, spec_file):
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
        path = spec_file(content)
        with pytest.raises(SpecValidationError) as exc:
            parse_spec(path)
        assert "Missing required section" in str(exc.value)

    def test_invalid_fmi_version(self, spec_file):
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
        path = spec_file(content)
        with pytest.raises(SpecValidationError) as exc:
            parse_spec(path)
        assert "fmi_version" in str(exc.value)

    def test_invalid_variable_type(self, spec_file):
        """VR-004: Invalid variable type → error"""
        content = """
[fmus]
a = { path = "/dev/null/a.fmu" }
[[connections]]
source = "a.x"
target = "a.y"
[[variables]]
name = "x"
type = "Complex"
causality = "input"
[solver]
type = "fixed_step"
step_size = 0.001
communication_step = 0.001
[wrapper]
communication_step = 0.001
"""
        path = spec_file(content)
        with pytest.raises(SpecValidationError) as exc:
            parse_spec(path)
        assert "type must be" in str(exc.value) and "Complex" in str(exc.value)

    def test_duplicate_variable_name(self, spec_file):
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
        path = spec_file(content)
        with pytest.raises(SpecValidationError) as exc:
            parse_spec(path)
        assert "duplicate variable name" in str(exc.value)

    def test_step_size_greater_than_comm_step(self, spec_file):
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
        path = spec_file(content)
        with pytest.raises(SpecValidationError) as exc:
            parse_spec(path)
        assert "step_size" in str(exc.value)

    def test_invalid_fmu_ref_format(self, spec_file):
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
        path = spec_file(content)
        with pytest.raises(SpecValidationError) as exc:
            parse_spec(path)
        assert "invalid format" in str(exc.value)

    def test_unknown_fmu_in_connection(self, spec_file):
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
        path = spec_file(content)
        with pytest.raises(SpecValidationError) as exc:
            parse_spec(path)
        assert "not defined" in str(exc.value)

    def test_algebraic_loop_config(self, spec_file):
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
        path = spec_file(content)
        spec = parse_spec(path)
        assert spec.solver.algebraic_loop.max_iterations == 50
        assert spec.solver.algebraic_loop.tolerance == 1e-8

    def test_comm_step_mismatch(self, spec_file):
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
        path = spec_file(content)
        with pytest.raises(SpecValidationError) as exc:
            parse_spec(path)
        assert "communication_step" in str(exc.value) and "equal" in str(exc.value)

    def test_spec_without_variables_section(self, spec_file):
        """Spec without [[variables]] should parse successfully (IMP-013)."""
        content = """
[metadata]
identifier = "test"

[fmus]
src = { path = "src.fmu" }
tgt = { path = "tgt.fmu" }

[[connections]]
source = "src.out"
target = "tgt.in"

[solver]
type = "fixed_step"
step_size = 0.001
communication_step = 0.001

[wrapper]
communication_step = 0.001
"""
        path = spec_file(content)
        spec = parse_spec(path)
        assert spec.variables == []  # Should be empty list, not error

    def test_integer_type_accepted(self, spec_file):
        """Integer type should be accepted (IC-006)."""
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
start = 42
[solver]
type = "fixed_step"
step_size = 0.001
communication_step = 0.001
[wrapper]
communication_step = 0.001
"""
        path = spec_file(content)
        spec = parse_spec(path)
        assert spec.variables[0].type == "Integer"
        assert spec.variables[0].start == 42

    def test_boolean_type_accepted(self, spec_file):
        """Boolean type should be accepted (IC-006)."""
        content = """
[fmus]
a = { path = "/dev/null/a.fmu" }
[[connections]]
source = "a.x"
target = "a.y"
[[variables]]
name = "x"
type = "Boolean"
causality = "input"
start = true
[solver]
type = "fixed_step"
step_size = 0.001
communication_step = 0.001
[wrapper]
communication_step = 0.001
"""
        path = spec_file(content)
        spec = parse_spec(path)
        assert spec.variables[0].type == "Boolean"
        assert spec.variables[0].start is True

    def test_string_type_accepted(self, spec_file):
        """String type should be accepted (IC-006)."""
        content = """
[fmus]
a = { path = "/dev/null/a.fmu" }
[[connections]]
source = "a.x"
target = "a.y"
[[variables]]
name = "x"
type = "String"
causality = "input"
start = "hello"
[solver]
type = "fixed_step"
step_size = 0.001
communication_step = 0.001
[wrapper]
communication_step = 0.001
"""
        path = spec_file(content)
        spec = parse_spec(path)
        assert spec.variables[0].type == "String"
        assert spec.variables[0].start == "hello"

    def test_invalid_start_type_for_real(self, spec_file):
        """String start for Real type should fail."""
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
start = "not_a_number"
[solver]
type = "fixed_step"
step_size = 0.001
communication_step = 0.001
[wrapper]
communication_step = 0.001
"""
        path = spec_file(content)
        with pytest.raises(SpecValidationError) as exc:
            parse_spec(path)
        assert "start" in str(exc.value)

    def test_spec_with_variables_section_still_works(self, spec_file):
        """Spec with [[variables]] should still parse correctly (backward compat)."""
        content = """
[metadata]
identifier = "test"

[fmus]
src = { path = "src.fmu" }

[[connections]]
source = "src.out"
target = "src.in"

[[variables]]
name = "my_input"
type = "Real"
causality = "input"
target = "src.some_input"

[solver]
type = "fixed_step"
step_size = 0.001
communication_step = 0.001

[wrapper]
communication_step = 0.001
"""
        path = spec_file(content)
        spec = parse_spec(path)
        assert len(spec.variables) == 1
        assert spec.variables[0].name == "my_input"