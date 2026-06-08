"""Tests for the mapper module."""
from __future__ import annotations

import os
import tempfile

import pytest

from tests.helpers import make_test_fmu
from cs_fmu_packager.errors import MappingError
from cs_fmu_packager.mapper import build_mapping
from cs_fmu_packager.models import (
    Connection,
    FmuRef,
    PackageSpec,
    SolverConfig,
    WrapperConfig,
    WrapperVariable,
)


def _create_test_fmu(path: str, name: str, guid: str, vars_xml: str) -> None:
    """Create a test FMU with given variables."""
    model_desc = f"""<?xml version="1.0" encoding="UTF-8"?>
<fmiModelDescription
  fmiVersion="2.0"
  modelName="{name}"
  guid="{guid}"
  generationTool="test"
  numberOfEventIndicators="0"
>
  <ModelExchange modelIdentifier="{name}" />
  <ModelVariables>
    {vars_xml}
  </ModelVariables>
</fmiModelDescription>"""

    make_test_fmu(path, model_desc)


_INPUT_VAR = '<ScalarVariable name="u" valueReference="0" causality="input"><Real start="0.0"/></ScalarVariable>'
_OUTPUT_VAR = '<ScalarVariable name="y" valueReference="1" causality="output"><Real/></ScalarVariable>'
_LOCAL_VAR = '<ScalarVariable name="x" valueReference="2" causality="local" variability="continuous"><Real start="0.0"/></ScalarVariable>'


@pytest.fixture
def fmus_dir():
    """Create temporary FMU files for testing."""
    d = tempfile.mkdtemp()
    yield d
    import shutil
    shutil.rmtree(d)


def _create_fmu_pair(fmus_dir: str):
    """Create source and target FMUs, return their paths."""
    src_path = os.path.join(fmus_dir, "src.fmu")
    tgt_path = os.path.join(fmus_dir, "tgt.fmu")
    _create_test_fmu(
        src_path, "SourceFMU", "{src-guid}",
        _INPUT_VAR + _OUTPUT_VAR + _LOCAL_VAR
    )
    _create_test_fmu(
        tgt_path, "TargetFMU", "{tgt-guid}",
        _INPUT_VAR + _OUTPUT_VAR + _LOCAL_VAR
    )
    return src_path, tgt_path


def test_basic_mapping(fmus_dir: str):
    """VR-002: Package two connected FMUs."""
    src_path, tgt_path = _create_fmu_pair(fmus_dir)
    spec = PackageSpec(
        fmus={
            "src": FmuRef(name="src", path=src_path),
            "tgt": FmuRef(name="tgt", path=tgt_path),
        },
        connections=[
            Connection(source_fmu="src", source_variable="y", target_fmu="tgt", target_variable="u"),
        ],
        variables=[
            WrapperVariable(name="input1", causality="input", target_fmu="src", target_variable="u"),
            WrapperVariable(name="output1", causality="output", source_fmu="tgt", source_variable="y"),
        ],
    )
    mapping = build_mapping(spec)
    assert len(mapping.fmus) == 2
    assert len(mapping.connections) == 1
    assert len(mapping.wrapper_inputs) == 1
    assert len(mapping.wrapper_outputs) == 1
    assert mapping.wrapper_inputs[0].wrapper_name == "input1"
    assert mapping.wrapper_outputs[0].wrapper_name == "output1"


def test_unknown_variable_reference(fmus_dir: str):
    """VR-004: Invalid variable reference → error."""
    src_path, tgt_path = _create_fmu_pair(fmus_dir)
    spec = PackageSpec(
        fmus={
            "src": FmuRef(name="src", path=src_path),
        },
        connections=[
            Connection(source_fmu="src", source_variable="nonexistent", target_fmu="src", target_variable="u"),
        ],
        variables=[],
    )
    with pytest.raises(MappingError) as exc:
        build_mapping(spec)
    assert "not found" in str(exc.value)
    assert "Connection 0:" in str(exc.value)


def test_unknown_fmu_in_connection(fmus_dir: str):
    """VR-004: Unknown FMU in connection."""
    src_path, tgt_path = _create_fmu_pair(fmus_dir)
    spec = PackageSpec(
        fmus={
            "src": FmuRef(name="src", path=src_path),
        },
        connections=[
            Connection(source_fmu="unknown", source_variable="y", target_fmu="src", target_variable="u"),
        ],
        variables=[],
    )
    with pytest.raises(MappingError) as exc:
        build_mapping(spec)
    assert "Connection 0:" in str(exc.value)


def test_parameter_mapping(fmus_dir: str):
    """Test parameter variable mapping."""
    src_path, _ = _create_fmu_pair(fmus_dir)
    spec = PackageSpec(
        fmus={
            "src": FmuRef(name="src", path=src_path),
        },
        connections=[],
        variables=[
            WrapperVariable(name="param1", causality="parameter", target_fmu="src", target_variable="u", start=5.0),
        ],
    )
    mapping = build_mapping(spec)
    assert len(mapping.wrapper_parameters) == 1
    assert mapping.wrapper_parameters[0].start == 5.0


def test_single_fmu_mapping(fmus_dir: str):
    """VR-001: Package one scalar FMU."""
    src_path, _ = _create_fmu_pair(fmus_dir)
    spec = PackageSpec(
        fmus={
            "src": FmuRef(name="src", path=src_path),
        },
        connections=[],
        variables=[
            WrapperVariable(name="input1", causality="input", target_fmu="src", target_variable="u"),
            WrapperVariable(name="output1", causality="output", source_fmu="src", source_variable="y"),
        ],
    )
    mapping = build_mapping(spec)
    assert len(mapping.fmus) == 1
    assert mapping.execution_order == ["src"] or "src" in mapping.execution_order
    assert len(mapping.algebraic_loops) == 0


def test_algebraic_loop_detection_internal(fmus_dir: str):
    """VR-008: SCC packaging (internal connections forming a loop)."""
    # Create FMU with both input and output
    src_path = os.path.join(fmus_dir, "a.fmu")
    tgt_path = os.path.join(fmus_dir, "b.fmu")
    vars_ab = _INPUT_VAR + _OUTPUT_VAR + _LOCAL_VAR
    _create_test_fmu(src_path, "FMU_A", "{guid-a}", vars_ab)
    _create_test_fmu(tgt_path, "FMU_B", "{guid-b}", vars_ab)

    # A.y -> B.u, B.y -> A.u (algebraic loop)
    spec = PackageSpec(
        fmus={
            "A": FmuRef(name="A", path=src_path),
            "B": FmuRef(name="B", path=tgt_path),
        },
        connections=[
            Connection(source_fmu="A", source_variable="y", target_fmu="B", target_variable="u"),
            Connection(source_fmu="B", source_variable="y", target_fmu="A", target_variable="u"),
        ],
        variables=[
            WrapperVariable(name="inp", causality="input", target_fmu="A", target_variable="u"),
            WrapperVariable(name="out", causality="output", source_fmu="B", source_variable="y"),
        ],
    )
    mapping = build_mapping(spec)
    # Should detect the SCC
    assert len(mapping.algebraic_loops) > 0
    # The SCC should contain both A and B
    scc_fmus = set()
    for loop in mapping.algebraic_loops:
        scc_fmus.update(loop.fmus)
    assert "A" in scc_fmus
    assert "B" in scc_fmus


def test_mapping_with_non_real_types(fmus_dir: str):
    """Test mapping with Integer/Boolean/String variable types."""
    src_path, tgt_path = _create_fmu_pair(fmus_dir)
    spec = PackageSpec(
        fmus={
            "src": FmuRef(name="src", path=src_path),
            "tgt": FmuRef(name="tgt", path=tgt_path),
        },
        connections=[
            Connection(source_fmu="src", source_variable="y", target_fmu="tgt", target_variable="u"),
        ],
        variables=[
            WrapperVariable(name="real_in", causality="input", type="Real", target_fmu="src", target_variable="u"),
            WrapperVariable(name="int_param", causality="parameter", type="Integer", target_fmu="src", target_variable="u", start=42),
            WrapperVariable(name="bool_out", causality="output", type="Boolean", source_fmu="tgt", source_variable="y"),
        ],
    )
    mapping = build_mapping(spec)
    # Find variables by name
    vars_by_name = {v.wrapper_name: v for v in mapping.all_variables()}
    assert vars_by_name["real_in"].variable_type == "Real"
    assert vars_by_name["int_param"].variable_type == "Integer"
    assert vars_by_name["int_param"].start == 42
    assert vars_by_name["bool_out"].variable_type == "Boolean"


def test_auto_discover_variables(fmus_dir: str):
    """build_mapping should auto-discover variables when spec has none (IMP-013)."""
    from cs_fmu_packager.mapper import _auto_discover_variables
    from cs_fmu_packager.models import FmuMetadata, ScalarVariable

    meta = FmuMetadata(
        model_identifier="test",
        fmi_version="2.0",
        guid="{test}",
        model_name="Test",
        variables={
            "in1": ScalarVariable(name="in1", value_reference=0, type="Real", causality="input"),
            "out1": ScalarVariable(name="out1", value_reference=1, type="Real", causality="output"),
            "param1": ScalarVariable(name="param1", value_reference=2, type="Real", causality="parameter"),
            "local1": ScalarVariable(name="local1", value_reference=3, type="Real", causality="local"),
        },
        )
    result = _auto_discover_variables({"fmu1": meta})
    # Should have 3 variables (input, output, parameter) — NOT local
    assert len(result) == 3
    # Check input
    inputs = [v for v in result if v.causality == "input"]
    assert len(inputs) == 1
    assert inputs[0].name == "in1"
    assert inputs[0].target_fmu == "fmu1"
    # Check output
    outputs = [v for v in result if v.causality == "output"]
    assert len(outputs) == 1
    assert outputs[0].name == "out1"
    assert outputs[0].source_fmu == "fmu1"
    # Check parameter
    params = [v for v in result if v.causality == "parameter"]
    assert len(params) == 1
    assert params[0].name == "param1"
    assert params[0].target_fmu == "fmu1"