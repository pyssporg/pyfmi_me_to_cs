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


def test_connection_direction_input_source_warns(fmus_dir: str):
    """Connection from an input-causality source is a warning, not an error."""
    src_path, tgt_path = _create_fmu_pair(fmus_dir)
    spec = PackageSpec(
        fmus={
            "src": FmuRef(name="src", path=src_path),
            "tgt": FmuRef(name="tgt", path=tgt_path),
        },
        connections=[
            Connection(source_fmu="src", source_variable="u", target_fmu="tgt", target_variable="u"),
        ],
        variables=[],
    )
    mapping = build_mapping(spec)
    assert any(
        "source variable has causality='input' (expected 'output' or 'local')" in w
        for w in mapping.warnings
    )


def test_connection_direction_output_target_warns(fmus_dir: str):
    """Connection to an output-causality target is a warning, not an error."""
    src_path, tgt_path = _create_fmu_pair(fmus_dir)
    spec = PackageSpec(
        fmus={
            "src": FmuRef(name="src", path=src_path),
            "tgt": FmuRef(name="tgt", path=tgt_path),
        },
        connections=[
            Connection(source_fmu="src", source_variable="y", target_fmu="tgt", target_variable="y"),
        ],
        variables=[],
    )
    mapping = build_mapping(spec)
    assert any(
        "target variable has causality='output' (expected 'input')" in w
        for w in mapping.warnings
    )


def test_connection_direction_well_formed_no_warning(fmus_dir: str):
    """Output -> input connection must not produce direction warnings."""
    src_path, tgt_path = _create_fmu_pair(fmus_dir)
    spec = PackageSpec(
        fmus={
            "src": FmuRef(name="src", path=src_path),
            "tgt": FmuRef(name="tgt", path=tgt_path),
        },
        connections=[
            Connection(source_fmu="src", source_variable="y", target_fmu="tgt", target_variable="u"),
        ],
        variables=[],
    )
    mapping = build_mapping(spec)
    assert not any("has causality" in w for w in mapping.warnings)


_BOOL_INPUT_VAR = '<ScalarVariable name="u" valueReference="0" causality="input"><Real start="0.0"/></ScalarVariable>'
_BOOL_OUTPUT_VAR = '<ScalarVariable name="b" valueReference="10" causality="output"><Boolean/></ScalarVariable>'
_INT_OUTPUT_VAR = '<ScalarVariable name="i" valueReference="11" causality="output"><Integer/></ScalarVariable>'
_REAL_INPUT_VAR = '<ScalarVariable name="u" valueReference="12" causality="input"><Real start="0.0"/></ScalarVariable>'


def test_non_real_connection_resolves_without_raising(fmus_dir: str):
    """Boolean/Integer outputs connect to Real inputs without mapping-time type checks.

    The C codegen routes all internal connections through getReal/setReal, so
    non-Real source variables are not rejected during mapping.
    """
    src_path = os.path.join(fmus_dir, "bool_src.fmu")
    tgt_path = os.path.join(fmus_dir, "real_tgt.fmu")
    _create_test_fmu(
        src_path, "BoolSource", "{bool-guid}", _BOOL_INPUT_VAR + _BOOL_OUTPUT_VAR + _INT_OUTPUT_VAR
    )
    _create_test_fmu(
        tgt_path, "RealTarget", "{real-guid}", _REAL_INPUT_VAR
    )
    spec = PackageSpec(
        fmus={
            "src": FmuRef(name="src", path=src_path),
            "tgt": FmuRef(name="tgt", path=tgt_path),
        },
        connections=[
            Connection(source_fmu="src", source_variable="b", target_fmu="tgt", target_variable="u"),
            Connection(source_fmu="src", source_variable="i", target_fmu="tgt", target_variable="u"),
        ],
        variables=[],
    )
    mapping = build_mapping(spec)
    assert len(mapping.connections) == 2
    by_source = {c.source_variable: c for c in mapping.connections}
    assert by_source["b"].source_value_reference == 10
    assert by_source["b"].target_value_reference == 12
    assert by_source["i"].source_value_reference == 11
    assert by_source["i"].target_value_reference == 12


def _create_test_fmu_with_desc(path: str, model_desc: str) -> None:
    """Write an FMU from a full modelDescription XML string."""
    make_test_fmu(path, model_desc)


def test_unsupported_feature_get_set_state_warns(fmus_dir: str):
    """ModelExchange with canGetAndSetFMUstate=false yields a warning."""
    model_desc = f"""<?xml version="1.0" encoding="UTF-8"?>
<fmiModelDescription
  fmiVersion="2.0"
  modelName="NoState"
  guid="{{no-state-guid}}"
  generationTool="test"
  numberOfEventIndicators="0"
>
  <ModelExchange modelIdentifier="NoState" canGetAndSetFMUstate="false" />
  <ModelVariables>
    {_INPUT_VAR}{_OUTPUT_VAR}
  </ModelVariables>
</fmiModelDescription>"""
    path = os.path.join(fmus_dir, "nostate.fmu")
    _create_test_fmu_with_desc(path, model_desc)
    spec = PackageSpec(
        fmus={"src": FmuRef(name="src", path=path)},
        connections=[],
        variables=[],
    )
    mapping = build_mapping(spec)
    assert any(
        "FMU 'src': FMU does not support get/set state" in w
        for w in mapping.warnings
    )


def test_unsupported_feature_event_indicators_warns(fmus_dir: str):
    """A modelDescription with numberOfEventIndicators>0 yields a warning."""
    model_desc = f"""<?xml version="1.0" encoding="UTF-8"?>
<fmiModelDescription
  fmiVersion="2.0"
  modelName="WithEvents"
  guid="{{events-guid}}"
  generationTool="test"
  numberOfEventIndicators="2"
>
  <ModelExchange modelIdentifier="WithEvents" />
  <ModelVariables>
    {_INPUT_VAR}{_OUTPUT_VAR}
  </ModelVariables>
</fmiModelDescription>"""
    path = os.path.join(fmus_dir, "events.fmu")
    _create_test_fmu_with_desc(path, model_desc)
    spec = PackageSpec(
        fmus={"src": FmuRef(name="src", path=path)},
        connections=[],
        variables=[],
    )
    mapping = build_mapping(spec)
    assert any(
        "FMU has 2 event indicators (event handling limited)" in w
        for w in mapping.warnings
    )


def test_wrapper_value_reference_assignment_order(fmus_dir: str):
    """wrapper_value_reference is assigned 1..N in inputs+outputs+parameters order."""
    src_path, tgt_path = _create_fmu_pair(fmus_dir)
    spec = PackageSpec(
        fmus={
            "src": FmuRef(name="src", path=src_path),
            "tgt": FmuRef(name="tgt", path=tgt_path),
        },
        connections=[],
        variables=[
            WrapperVariable(name="in1", causality="input", target_fmu="src", target_variable="u"),
            WrapperVariable(name="out1", causality="output", source_fmu="src", source_variable="y"),
            WrapperVariable(name="param1", causality="parameter", target_fmu="tgt", target_variable="u", start=1.0),
            WrapperVariable(name="in2", causality="input", target_fmu="tgt", target_variable="u"),
            WrapperVariable(name="out2", causality="output", source_fmu="tgt", source_variable="y"),
        ],
    )
    mapping = build_mapping(spec)
    vars_all = mapping.all_variables()
    assert len(vars_all) == 8
    assert [v.wrapper_value_reference for v in vars_all] == [1, 2, 3, 4, 5, 6, 7, 8]
    assert [v.wrapper_name for v in vars_all] == [
        "in1", "in2", "out1", "out2", "param1",
        "solver.type", "solver.tolerance", "solver.step_size",
    ]


def test_auto_discover_variables(fmus_dir: str):
    """build_mapping should auto-discover variables when spec has none (IMP-013)."""
    from cs_fmu_packager.mapper import _auto_discover_variables
    from pyssp_standard.standard.fmi2.model.model_description import (
        Fmi2ModelDescriptionDocument, Fmi2ScalarVariable,
    )

    in1 = Fmi2ScalarVariable(name="in1", value_reference=0, type_name="Real", causality="input")
    out1 = Fmi2ScalarVariable(name="out1", value_reference=1, type_name="Real", causality="output")
    param1 = Fmi2ScalarVariable(name="param1", value_reference=2, type_name="Real", causality="parameter")
    local1 = Fmi2ScalarVariable(name="local1", value_reference=3, type_name="Real", causality="local")
    doc = Fmi2ModelDescriptionDocument(
        root=None, fmi_version="2.0", model_name="Test", guid="{test}",
        variables=[in1, out1, param1, local1],
        unit_definitions=[], type_definitions=[], model_structure=None,
    )
    result = _auto_discover_variables({"fmu1": doc})
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