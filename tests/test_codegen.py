"""Tests for code generation (golden-file style)."""
from __future__ import annotations

import os
import re
import tempfile
from xml.etree import ElementTree as ET

import pytest

from cs_fmu_packager.codegen.cmake import generate_cmake
from cs_fmu_packager.codegen.fixed_point import generate_fixed_point_impl
from cs_fmu_packager.codegen.fmi_interface import generate_fmi_interface_impl
from cs_fmu_packager.codegen.solver import generate_solver_impl
from cs_fmu_packager.mapper import _auto_discover_variables, build_mapping
from cs_fmu_packager.model_description import generate_model_description
from cs_fmu_packager.models import (
    AlgebraicLoop,
    Connection,
    FmuRef,
    MappingTable,
    MappedVariable,
    PackageSpec,
    ResolvedConnection,
    SolverConfig,
    WrapperConfig,
    WrapperVariable,
)
from pyssp_standard.standard.fmi2.codec.model_description_xml_codec import (
    Fmi2ModelDescriptionXmlCodec,
)
from pyssp_standard.standard.fmi2.model.model_description import (
    Fmi2InterfaceAttributes,
    Fmi2ModelDescriptionDocument,
    Fmi2ScalarVariable,
)
from tests.helpers import make_test_fmu


@pytest.fixture
def sample_spec() -> PackageSpec:
    return PackageSpec(
        metadata={"identifier": "test_fmu"},
        fmus={
            "src": FmuRef(name="src", path="/fake/src.fmu"),
            "tgt": FmuRef(name="tgt", path="/fake/tgt.fmu"),
        },
        solver=SolverConfig(type="fixed_step", step_size=0.001, communication_step=0.01),
        wrapper=WrapperConfig(communication_step=0.01),
    )


@pytest.fixture
def sample_mapping() -> MappingTable:
    src_vars = [
        Fmi2ScalarVariable(name="u", value_reference=0, type_name="Real", causality="input"),
        Fmi2ScalarVariable(name="y", value_reference=1, type_name="Real", causality="output"),
    ]
    tgt_vars = [
        Fmi2ScalarVariable(name="u", value_reference=0, type_name="Real", causality="input"),
        Fmi2ScalarVariable(name="y", value_reference=1, type_name="Real", causality="output"),
    ]
    from pyssp_standard.standard.fmi2.model.model_description import Fmi2InterfaceAttributes
    return MappingTable(
        fmus={
            "src": Fmi2ModelDescriptionDocument(
                root=None, fmi_version="2.0", guid="{src-guid}", model_name="SrcFMU",
                variables=src_vars, unit_definitions=[], type_definitions=[],
                model_structure=None,
                capabilities=Fmi2InterfaceAttributes(model_identifier="src_model"),
            ),
            "tgt": Fmi2ModelDescriptionDocument(
                root=None, fmi_version="2.0", guid="{tgt-guid}", model_name="TgtFMU",
                variables=tgt_vars, unit_definitions=[], type_definitions=[],
                model_structure=None,
                capabilities=Fmi2InterfaceAttributes(model_identifier="tgt_model"),
            ),
        },
        wrapper_inputs=[
            MappedVariable(
                wrapper_name="input1", variable_type="Real", causality="input",
                target_fmu="src", target_variable="u", target_value_reference=0,
            ),
        ],
        wrapper_outputs=[
            MappedVariable(
                wrapper_name="output1", variable_type="Real", causality="output",
                source_fmu="tgt", source_variable="y", source_value_reference=1,
            ),
        ],
        connections=[
            ResolvedConnection(
                source_fmu="src", source_variable="y", source_value_reference=1,
                target_fmu="tgt", target_variable="u", target_value_reference=0,
            ),
        ],
    )


class TestCmakeCodegen:
    def test_generate_cmake(self, sample_spec, sample_mapping):
        content = generate_cmake(sample_mapping, sample_spec)
        assert "cmake_minimum_required(VERSION 3.22)" in content
        assert "find_package(SUNDIALS REQUIRED COMPONENTS arkode cvode sunlinsoldense sunmatrixdense nvecserial)" in content
        assert "fmi2_interface.c" in content
        assert "solver_integration.c" in content
        assert "fixed_point_iteration.c" in content
        assert "binaries/linux64" in content
        assert "SHARED" in content
        # IMP-003: header directories point flat at build directory root
        assert 'set(FMI_HEADERS_DIR "${CMAKE_CURRENT_SOURCE_DIR}")' in content
        assert 'set(WRAPPER_HEADERS_DIR "${CMAKE_CURRENT_SOURCE_DIR}")' in content


class TestModelDescriptionCodegen:
    def test_generate_model_description(self, sample_spec, sample_mapping):
        """VR-007: Metadata contains solver policy + FMU mapping."""
        content = generate_model_description(sample_spec, sample_mapping)
        assert "fmiVersion=\"2.0\"" in content
        assert "CoSimulation" in content
        assert "modelIdentifier=\"test_fmu\"" in content
        assert "CsFmuPackager" in content
        assert "solverType=\"fixed_step\"" in content
        assert "solverStepSize=\"0.001\"" in content
        assert "communicationStepSize=\"0.01\"" in content
        assert "internalFMUs=" in content
        assert "input1" in content
        assert "output1" in content
        assert "Connection" in content

    def test_variable_preservation(self, sample_spec, sample_mapping):
        """VR-003: Expose wrapper inputs/outputs with stable names."""
        content = generate_model_description(sample_spec, sample_mapping)
        assert 'name="input1"' in content
        assert 'name="output1"' in content
        assert 'causality="input"' in content
        assert 'causality="output"' in content

    def test_guid_deterministic(self, sample_spec, sample_mapping):
        """GUID should be deterministic from same spec."""
        content1 = generate_model_description(sample_spec, sample_mapping)
        content2 = generate_model_description(sample_spec, sample_mapping)
        # Extract GUIDs
        import re
        guid1 = re.search(r'guid="([^"]+)"', content1).group(1)
        guid2 = re.search(r'guid="([^"]+)"', content2).group(1)
        assert guid1 == guid2

    def test_guid_sensitive_to_variable_content(self, sample_spec, sample_mapping):
        """Two specs with the same counts but different variable content differ in GUID."""
        import re
        from cs_fmu_packager.model_description import _derive_guid

        spec_a = PackageSpec(
            metadata={"identifier": "guid_a"},
            fmus=sample_spec.fmus,
            solver=SolverConfig(type="fixed_step", step_size=0.001, communication_step=0.01),
            wrapper=WrapperConfig(communication_step=0.01),
        )
        spec_b = PackageSpec(
            metadata={"identifier": "guid_b"},
            fmus=sample_spec.fmus,
            solver=SolverConfig(type="fixed_step", step_size=0.001, communication_step=0.01),
            wrapper=WrapperConfig(communication_step=0.01),
        )
        # Same number of variables (1 input, 1 output) but different content.
        spec_a.variables = [
            WrapperVariable(name="input1", causality="input", target_fmu="src", target_variable="u"),
            WrapperVariable(name="output1", causality="output", source_fmu="tgt", source_variable="y"),
        ]
        spec_b.variables = [
            WrapperVariable(name="foo", causality="input", target_fmu="src", target_variable="u"),
            WrapperVariable(name="bar", causality="output", source_fmu="tgt", source_variable="y"),
        ]
        assert spec_a.metadata != spec_b.metadata
        assert len(spec_a.variables) == len(spec_b.variables)
        guid_a = _derive_guid(spec_a)
        guid_b = _derive_guid(spec_b)
        assert guid_a != guid_b

    def test_guid_sensitive_to_connection_content(self, sample_spec, sample_mapping):
        """Two specs differing only in a connection endpoint produce different GUIDs."""
        from cs_fmu_packager.model_description import _derive_guid

        def _spec(conn) -> PackageSpec:
            s = PackageSpec(
                metadata={"identifier": "guid_conn"},
                fmus=sample_spec.fmus,
                connections=[conn],
                variables=[],
                solver=SolverConfig(type="fixed_step", step_size=0.001, communication_step=0.01),
                wrapper=WrapperConfig(communication_step=0.01),
            )
            return s

        conn_a = Connection(source_fmu="src", source_variable="y", target_fmu="tgt", target_variable="u")
        conn_b = Connection(source_fmu="src", source_variable="y", target_fmu="tgt", target_variable="u")
        # Same endpoints but... to differ we need a different endpoint; use the
        # same count (1 connection) but a different variable.
        conn_c = Connection(source_fmu="src", source_variable="y", target_fmu="tgt", target_variable="u")
        conn_d = Connection(source_fmu="tgt", source_variable="y", target_fmu="src", target_variable="u")
        assert _derive_guid(_spec(conn_a)) == _derive_guid(_spec(conn_b))  # identical → same
        assert _derive_guid(_spec(conn_c)) != _derive_guid(_spec(conn_d))  # different → different

    def test_non_real_type_xml(self, sample_spec, sample_mapping):
        """IC-006: Non-Real types produce correct XML sub-elements."""
        # Add Integer/Boolean/String variables to the mapping
        from cs_fmu_packager.models import MappedVariable
        mapping = sample_mapping
        mapping.wrapper_inputs.append(
            MappedVariable(
                wrapper_name="int_input", variable_type="Integer", causality="input",
                start=42,
            )
        )
        mapping.wrapper_inputs.append(
            MappedVariable(
                wrapper_name="bool_input", variable_type="Boolean", causality="input",
                start=True,
            )
        )
        mapping.wrapper_inputs.append(
            MappedVariable(
                wrapper_name="str_input", variable_type="String", causality="input",
                start="hello",
            )
        )
        content = generate_model_description(sample_spec, mapping)
        assert '<Integer start="42" />' in content
        assert '<Boolean start="true" />' in content
        assert '<String start="hello" />' in content
        assert 'name="int_input"' in content
        assert 'name="bool_input"' in content
        assert 'name="str_input"' in content

    def test_codegen_with_auto_discovered_variables(self):
        """Codegen should work with auto-discovered variables (empty spec.variables)."""
        spec = PackageSpec(
            metadata={"identifier": "auto_test"},
            fmus={"fmu1": FmuRef(name="fmu1", path="/fake/fmu1.fmu")},
            connections=[],
            variables=[],  # Empty — simulates auto-discovery
            solver=SolverConfig(type="fixed_step", step_size=0.001, communication_step=0.001),
            wrapper=WrapperConfig(communication_step=0.001),
        )
        doc = Fmi2ModelDescriptionDocument(
            root=None, fmi_version="2.0", model_name="AutoFMU", guid="{auto}",
            variables=[
                Fmi2ScalarVariable(name="in1", value_reference=0, type_name="Real", causality="input"),
                Fmi2ScalarVariable(name="out1", value_reference=1, type_name="Real", causality="output"),
                Fmi2ScalarVariable(name="param1", value_reference=2, type_name="Real", causality="parameter"),
            ],
            unit_definitions=[], type_definitions=[], model_structure=None,
            capabilities=Fmi2InterfaceAttributes(model_identifier="auto_model"),
        )

        # Resolve auto-discovered variables the way build_mapping would.
        discovered = _auto_discover_variables({"fmu1": doc})
        doc_vars = {v.name: v for v in doc.variables}
        wrapper_inputs, wrapper_outputs, wrapper_parameters = [], [], []
        for wv in discovered:
            mapped = MappedVariable(
                wrapper_name=wv.name,
                variable_type=wv.type,
                causality=wv.causality,
                target_fmu=wv.target_fmu,
                target_variable=wv.target_variable,
                target_value_reference=(
                    doc_vars[wv.target_variable].value_reference
                    if wv.target_variable else None
                ),
                source_fmu=wv.source_fmu,
                source_variable=wv.source_variable,
                source_value_reference=(
                    doc_vars[wv.source_variable].value_reference
                    if wv.source_variable else None
                ),
            )
            if wv.causality == "input":
                wrapper_inputs.append(mapped)
            elif wv.causality == "output":
                wrapper_outputs.append(mapped)
            else:
                wrapper_parameters.append(mapped)

        mapping = MappingTable(
            fmus={"fmu1": doc},
            wrapper_inputs=wrapper_inputs,
            wrapper_outputs=wrapper_outputs,
            wrapper_parameters=wrapper_parameters,
            execution_order=["fmu1"],
        )

        model_xml = generate_model_description(spec, mapping)
        for name in ("in1", "out1", "param1"):
            assert f'name="{name}"' in model_xml

        interface_c = generate_fmi_interface_impl(spec, mapping)
        # The C snippet addresses boundary variables by array index ([j].vr) and
        # per-type role, so assert the wiring derived from the auto-discovery:
        # exactly one real input, one real output, and one real parameter.
        assert "inst->num_real_inputs = 1;" in interface_c
        assert "inst->num_real_outputs = 1;" in interface_c
        assert "inst->num_real_params = 1;" in interface_c
        assert "inst->real_inputs[0].vr = 1;" in interface_c
        assert "inst->real_outputs[0].vr = 1;" in interface_c
        assert "inst->real_params[0].vr = 1;" in interface_c


class TestCHeadersResolution:
    """Verify c_headers resolution logic (IMP-005)."""

    def test_default_resolution_via_package_data(self):
        """Package-data c_headers should be discoverable via importlib.resources."""
        from cs_fmu_packager.cli import _resolve_c_headers_dir
        path = _resolve_c_headers_dir(None)
        assert os.path.isdir(path), f"Resolved path {path} is not a directory"
        for hdr in ("fmi2Functions.h", "fmi2FunctionTypes.h", "fmi2TypesPlatform.h"):
            assert os.path.exists(os.path.join(path, hdr)), \
                f"Missing header {hdr} in resolved path {path}"

    def test_explicit_c_headers_override(self, tmp_path):
        """Explicit --c-headers path should be used when provided."""
        from cs_fmu_packager.cli import _resolve_c_headers_dir
        hdr_dir = tmp_path / "custom_headers"
        hdr_dir.mkdir()
        (hdr_dir / "fmi2Functions.h").write_text("// fake")
        (hdr_dir / "fmi2FunctionTypes.h").write_text("// fake")
        (hdr_dir / "fmi2TypesPlatform.h").write_text("// fake")
        path = _resolve_c_headers_dir(str(hdr_dir))
        assert path == str(hdr_dir)

    def test_invalid_c_headers_raises_error(self, tmp_path):
        """Invalid --c-headers path should raise BuildError."""
        from cs_fmu_packager.cli import _resolve_c_headers_dir
        from cs_fmu_packager.errors import BuildError
        with pytest.raises(BuildError):
            _resolve_c_headers_dir(str(tmp_path / "nonexistent"))


class TestGenerateAll:
    """Code-generation orchestration (wrapper.py)."""

    def test_generate_all_writes_expected_files(self, sample_spec, sample_mapping, tmp_path):
        from cs_fmu_packager.codegen.wrapper import generate_all
        from cs_fmu_packager.cli import _resolve_c_headers_dir

        out_dir = str(tmp_path / "gen")
        headers = _resolve_c_headers_dir(None)
        generated = generate_all(sample_spec, sample_mapping, out_dir, headers)
        for fname in (
            "CMakeLists.txt",
            "modelDescription.xml",
            "fmi2_interface.c",
            "solver_integration.c",
            "fixed_point_iteration.c",
            "fmi2Functions.h",
            "fmi2TypesPlatform.h",
            "fmi2FunctionTypes.h",
        ):
            path = os.path.join(out_dir, fname)
            assert os.path.isfile(path), f"missing {path}"
            assert generated[path] is not None
        # Codegen headers are copied too.
        codegen_headers = [p for p in os.listdir(out_dir) if p.endswith(".h")]
        assert "fmi2_interface.h" in codegen_headers

    def test_missing_headers_raise_codegen_error(self, sample_spec, sample_mapping, tmp_path):
        from cs_fmu_packager.codegen.wrapper import generate_all
        from cs_fmu_packager.errors import CodegenError

        empty_headers = tmp_path / "no_headers"
        empty_headers.mkdir()
        with pytest.raises(CodegenError) as exc:
            generate_all(
                sample_spec, sample_mapping,
                str(tmp_path / "gen"), str(empty_headers),
            )
        assert "Missing required FMI 2.0 header file(s)" in str(exc.value)
        assert "fmi2Functions.h" in str(exc.value)


@pytest.fixture
def full_type_mapping() -> MappingTable:
    from pyssp_standard.standard.fmi2.model.model_description import Fmi2InterfaceAttributes
    all_vars = [
        Fmi2ScalarVariable(name='u_r', value_reference=0, type_name='Real', causality='input'),
        Fmi2ScalarVariable(name='u_i', value_reference=1, type_name='Integer', causality='input'),
        Fmi2ScalarVariable(name='u_b', value_reference=2, type_name='Boolean', causality='input'),
        Fmi2ScalarVariable(name='u_s', value_reference=3, type_name='String', causality='input'),
        Fmi2ScalarVariable(name='y_r', value_reference=10, type_name='Real', causality='output'),
        Fmi2ScalarVariable(name='y_i', value_reference=11, type_name='Integer', causality='output'),
        Fmi2ScalarVariable(name='y_b', value_reference=12, type_name='Boolean', causality='output'),
        Fmi2ScalarVariable(name='y_s', value_reference=13, type_name='String', causality='output'),
        Fmi2ScalarVariable(name='p_r', value_reference=20, type_name='Real', causality='parameter'),
        Fmi2ScalarVariable(name='p_i', value_reference=21, type_name='Integer', causality='parameter'),
        Fmi2ScalarVariable(name='p_b', value_reference=22, type_name='Boolean', causality='parameter'),
        Fmi2ScalarVariable(name='p_s', value_reference=23, type_name='String', causality='parameter'),
    ]
    src_fmu = Fmi2ModelDescriptionDocument(
        root=None, fmi_version='2.0', guid='{src-guid}', model_name='SrcFMU',
        variables=all_vars, unit_definitions=[], type_definitions=[],
        model_structure=None,
        capabilities=Fmi2InterfaceAttributes(model_identifier='src_model'),
    )
    tgt_fmu = Fmi2ModelDescriptionDocument(
        root=None, fmi_version='2.0', guid='{tgt-guid}', model_name='TgtFMU',
        variables=[], unit_definitions=[], type_definitions=[],
        model_structure=None,
        capabilities=Fmi2InterfaceAttributes(model_identifier='tgt_model'),
    )
    mapping = MappingTable(
        fmus={'src': src_fmu, 'tgt': tgt_fmu},
        wrapper_inputs=[
            MappedVariable(wrapper_name='in_r', variable_type='Real', causality='input', target_fmu='src', target_variable='u_r', target_value_reference=0),
            MappedVariable(wrapper_name='in_i', variable_type='Integer', causality='input', target_fmu='src', target_variable='u_i', target_value_reference=1),
            MappedVariable(wrapper_name='in_b', variable_type='Boolean', causality='input', target_fmu='src', target_variable='u_b', target_value_reference=2),
            MappedVariable(wrapper_name='in_s', variable_type='String', causality='input', target_fmu='src', target_variable='u_s', target_value_reference=3),
        ],
        wrapper_outputs=[
            MappedVariable(wrapper_name='out_r', variable_type='Real', causality='output', source_fmu='src', source_variable='y_r', source_value_reference=10),
            MappedVariable(wrapper_name='out_i', variable_type='Integer', causality='output', source_fmu='src', source_variable='y_i', source_value_reference=11),
            MappedVariable(wrapper_name='out_b', variable_type='Boolean', causality='output', source_fmu='src', source_variable='y_b', source_value_reference=12),
            MappedVariable(wrapper_name='out_s', variable_type='String', causality='output', source_fmu='src', source_variable='y_s', source_value_reference=13),
        ],
        wrapper_parameters=[
            MappedVariable(wrapper_name='param_r', variable_type='Real', causality='parameter', target_fmu='src', target_variable='p_r', target_value_reference=20),
            MappedVariable(wrapper_name='param_i', variable_type='Integer', causality='parameter', target_fmu='src', target_variable='p_i', target_value_reference=21, start=99),
            MappedVariable(wrapper_name='param_b', variable_type='Boolean', causality='parameter', target_fmu='src', target_variable='p_b', target_value_reference=22, start=True),
            MappedVariable(wrapper_name='param_s', variable_type='String', causality='parameter', target_fmu='src', target_variable='p_s', target_value_reference=23, start='default'),
        ],
        connections=[],
    )
    return mapping


class TestFmiInterfaceCodegen:
    """Tests for fmi2_interface.c generation."""

    def test_internal_fmu_load_path(self, sample_spec, sample_mapping):
        """Generated C code uses modelIdentifier-based path, not wildcard."""
        content = generate_fmi_interface_impl(sample_spec, sample_mapping)
        # Should NOT contain wildcard *.so in the dlopen path
        assert '*.so"' not in content, "Wildcard *.so should not appear in dlopen path"
        # Should contain the resolved model identifier paths
        assert "src_model.so" in content
        assert "tgt_model.so" in content

    def test_generated_output_unchanged(self, sample_spec, full_type_mapping):
        """IMP-020/IMP-021: Generated C output must remain byte-identical."""
        import pathlib
        from cs_fmu_packager.codegen.fmi_interface import generate_fmi_interface_impl
        golden_path = pathlib.Path(__file__).parent / "golden" / "fmi2_interface_test_fmu.c"
        content = generate_fmi_interface_impl(sample_spec, full_type_mapping)
        assert content == golden_path.read_text(), (
            "Generated C output changed. "
            "If the change is intentional, regenerate the golden file:\n"
            f"  {golden_path}\n"
        )


class TestSolverCodegen:
    """Tests for solver_integration.c generation."""

    def test_generate_solver_impl(self, sample_spec, sample_mapping):
        """ARKODE wrapper includes header, init, step, combined RHS, and header comment."""
        content = generate_solver_impl(sample_spec, sample_mapping)
        assert '#include "solver_integration.h"' in content
        assert "int solver_init(WrapperInstance* wrapper)" in content
        assert "solver_step" in content
        assert "combined_rhs" in content
        assert "ARKStepCreate" in content
        assert "Generated by cs-fmu-packager for: test_fmu" in content
        assert "Total continuous states: 0" in content
        # combined_rhs must couple the internal FMUs at every stage, not just
        # concatenate their derivatives.
        assert '#include "fixed_point_iteration.h"' in content
        assert "wrapper_resolve_coupling(wrapper" in content

    def test_solver_step_mode_branch(self, sample_spec, sample_mapping):
        """Fixed-step default uses ARKodeSetFixedStep; variable-step uses tolerances."""
        content = generate_solver_impl(sample_spec, sample_mapping)
        assert "SOLVER_TYPE_VARIABLE_STEP" in content
        assert "ARKodeSStolerances" in content
        assert "ARKodeSetFixedStep" in content

    def test_solver_dispatch(self, sample_spec, sample_mapping):
        """All configured solver types are wired into solver_init."""
        content = generate_solver_impl(sample_spec, sample_mapping)
        assert "SOLVER_TYPE_FIXED_STEP" in content
        assert "SOLVER_TYPE_FIXED_RK2" in content
        assert "SOLVER_TYPE_FIXED_RK4" in content
        assert "SOLVER_TYPE_BACKWARD_EULER" in content
        assert "SOLVER_TYPE_CVODE" in content
        assert "ARKStepCreate(NULL, combined_rhs" in content  # implicit Euler
        assert "CVodeCreate(CV_ADAMS" in content
        assert "CVode(" in content  # CVODE evolve call in solver_step
        assert "CVodeFree" in content
        assert "CVodeSStolerances" in content
        assert "ARKodeSetOrder" in content

    def test_solver_step_reports_actual_time(self, sample_spec, sample_mapping):
        """solver_step exposes the time actually reached through t_out."""
        content = generate_solver_impl(sample_spec, sample_mapping)
        assert "int solver_step(WrapperInstance* wrapper, double t0, double h, double* t_out)" in content
        assert "*t_out = (double)t_ret;" in content

    def test_continuous_state_count_from_local_variables(self):
        """Local continuous variables (excluding der(...)) count as states."""
        doc = Fmi2ModelDescriptionDocument(
            root=None, fmi_version="2.0", guid="{g}", model_name="TestFMU",
            variables=[
                Fmi2ScalarVariable(name="x", value_reference=0, type_name="Real",
                                   causality="local", variability="continuous"),
                Fmi2ScalarVariable(name="der(x)", value_reference=1, type_name="Real",
                                   causality="local", variability="continuous"),
            ],
            unit_definitions=[], type_definitions=[], model_structure=None,
        )
        spec = PackageSpec(
            metadata={"identifier": "test_fmu"},
            fmus={"fmu1": FmuRef(name="fmu1", path="/fake/fmu1.fmu")},
            solver=SolverConfig(),
            wrapper=WrapperConfig(),
        )
        mapping = MappingTable(fmus={"fmu1": doc}, execution_order=["fmu1"])
        content = generate_solver_impl(spec, mapping)
        assert "Total continuous states: 1" in content
        assert "fmu1: TestFMU, nx=1" in content


class TestFixedPointCodegen:
    """Tests for fixed_point_iteration.c generation."""

    def test_generate_fixed_point_impl(self, sample_spec, sample_mapping):
        content = generate_fixed_point_impl(sample_spec, sample_mapping)
        assert "fixed_point_solve_loop" in content
        assert "wrapper_resolve_coupling" in content
        assert "wrapper_propagate_connections" in content
        assert "Algebraic loops detected: 0" in content

    def test_algebraic_loop_parameters_and_wiring(self):
        """Loop detection, max_iterations/tolerance, and fmi2_interface wiring."""
        spec = PackageSpec(
            metadata={"identifier": "loop_test"},
            fmus={
                "A": FmuRef(name="A", path="/fake/a.fmu"),
                "B": FmuRef(name="B", path="/fake/b.fmu"),
            },
            solver=SolverConfig(type="fixed_step", step_size=0.001, communication_step=0.01),
            wrapper=WrapperConfig(communication_step=0.01),
        )
        spec.solver.algebraic_loop.max_iterations = 50
        spec.solver.algebraic_loop.tolerance = 1e-8

        def _doc(name: str, model_identifier: str) -> Fmi2ModelDescriptionDocument:
            return Fmi2ModelDescriptionDocument(
                root=None, fmi_version="2.0", guid=f"{{{name}}}", model_name=name,
                variables=[
                    Fmi2ScalarVariable(name="u", value_reference=0, type_name="Real", causality="input"),
                    Fmi2ScalarVariable(name="y", value_reference=1, type_name="Real", causality="output"),
                ],
                unit_definitions=[], type_definitions=[], model_structure=None,
                capabilities=Fmi2InterfaceAttributes(model_identifier=model_identifier),
            )

        conn_ab = ResolvedConnection(
            source_fmu="A", source_variable="y", source_value_reference=1,
            target_fmu="B", target_variable="u", target_value_reference=0,
        )
        conn_ba = ResolvedConnection(
            source_fmu="B", source_variable="y", source_value_reference=1,
            target_fmu="A", target_variable="u", target_value_reference=0,
        )
        mapping = MappingTable(
            fmus={"A": _doc("FMU_A", "a_model"), "B": _doc("FMU_B", "b_model")},
            wrapper_inputs=[
                MappedVariable(wrapper_name="input1", variable_type="Real", causality="input",
                               target_fmu="A", target_variable="u", target_value_reference=0),
            ],
            wrapper_outputs=[
                MappedVariable(wrapper_name="output1", variable_type="Real", causality="output",
                               source_fmu="B", source_variable="y", source_value_reference=1),
            ],
            connections=[conn_ab, conn_ba],
            algebraic_loops=[
                AlgebraicLoop(fmus=["A", "B"], connections=[conn_ab, conn_ba]),
            ],
        )

        content = generate_fixed_point_impl(spec, mapping)
        assert "Algebraic loops detected: 1" in content
        assert "Max iterations: 50, Tolerance: 1e-08" in content

        interface = generate_fmi_interface_impl(spec, mapping)
        assert "wrapper_resolve_coupling(inst" in interface
        assert "wrapper_propagate_connections(inst)" in interface
        assert "inst->num_algebraic_loops = 1;" in interface
        assert "inst->algebraic_loop_max_iterations = 50;" in interface
        assert "inst->algebraic_loop_tolerance = 1e-08;" in interface


class TestBoundaryValueReferenceConsistency:
    """Wrapper valueReference ordering invariant: mapper, XML, and C init code."""

    @pytest.fixture
    def fmu_dir(self, tmp_path) -> str:
        return str(tmp_path)

    @staticmethod
    def _write_test_fmu(path: str, name: str, guid: str, vars_xml: str) -> None:
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

    def test_value_reference_ordering_consistency(self, fmu_dir):
        real_input = '<ScalarVariable name="u" valueReference="0" causality="input"><Real/></ScalarVariable>'
        real_output = '<ScalarVariable name="y" valueReference="1" causality="output"><Real/></ScalarVariable>'
        src_path = os.path.join(fmu_dir, "src.fmu")
        tgt_path = os.path.join(fmu_dir, "tgt.fmu")
        self._write_test_fmu(src_path, "SourceFMU", "{src-guid}", real_input + real_output)
        self._write_test_fmu(tgt_path, "TargetFMU", "{tgt-guid}", real_input + real_output)

        spec = PackageSpec(
            metadata={"identifier": "vr_order"},
            fmus={
                "src": FmuRef(name="src", path=src_path),
                "tgt": FmuRef(name="tgt", path=tgt_path),
            },
            connections=[
                Connection(source_fmu="src", source_variable="y", target_fmu="tgt", target_variable="u"),
            ],
            # Shuffled causality order — grouping must happen inside build_mapping.
            variables=[
                WrapperVariable(name="output1", causality="output", source_fmu="tgt", source_variable="y"),
                WrapperVariable(name="input1", causality="input", target_fmu="src", target_variable="u"),
                WrapperVariable(name="param1", causality="parameter", target_fmu="src", target_variable="u"),
                WrapperVariable(name="input2", causality="input", target_fmu="tgt", target_variable="u"),
                WrapperVariable(name="output2", causality="output", source_fmu="src", source_variable="y"),
            ],
            solver=SolverConfig(),
            wrapper=WrapperConfig(),
        )
        mapping = build_mapping(spec)
        all_vars = mapping.all_variables()
        n_vars = len(all_vars)
        assert n_vars == 8

        # Mapper assigns 1..N in all_variables() (inputs, outputs, params) order.
        assert [m.wrapper_value_reference for m in all_vars] == list(range(1, n_vars + 1))

        # modelDescription.xml: ScalarVariable elements appear in the same order,
        # with the same value references.
        xml = generate_model_description(spec, mapping)
        root = ET.fromstring(xml)
        scalar_vars = list(root.find("ModelVariables").findall("ScalarVariable"))
        assert [sv.get("name") for sv in scalar_vars] == [m.wrapper_name for m in all_vars]
        assert [int(sv.get("valueReference")) for sv in scalar_vars] == [
            m.wrapper_value_reference for m in all_vars
        ]

        # C init code: the per-type vr assignments reference the same 1..N set
        # with no duplicates.
        interface = generate_fmi_interface_impl(spec, mapping)
        vr_values = [
            int(match.group(1))
            for match in re.finditer(
                r"inst->\w+_(?:inputs|outputs|params)\[\d+\]\.vr = (\d+);", interface
            )
        ]
        assert sorted(vr_values) == list(range(1, n_vars + 1))
        assert len(set(vr_values)) == n_vars


class TestModelDescriptionRoundTrip:
    """Round-trip the generated modelDescription.xml through an FMI 2 parser."""

    def test_pyssp_model_description_round_trip(self, sample_spec, sample_mapping):
        xml = generate_model_description(sample_spec, sample_mapping)
        # Must at least be well-formed XML.
        ET.fromstring(xml)
        # Re-parse through pyssp_standard's FMI 2.0 model-description codec.
        doc = Fmi2ModelDescriptionXmlCodec().parse(xml)
        assert doc.fmi_version == "2.0"
        assert doc.interface_type == "CoSimulation"
        assert doc.model_name == "test_fmu"
        assert [v.name for v in doc.variables] == ["input1", "output1"]
        assert [v.value_reference for v in doc.variables] == [1, 2]


class TestReservedSolverParameters:
    """Master-visible solver knobs: solver.type / solver.tolerance / solver.step_size."""

    @pytest.fixture
    def reserved_mapping(self, sample_spec, sample_mapping) -> MappingTable:
        from cs_fmu_packager.models import build_reserved_parameters
        mapping = MappingTable(
            fmus=sample_mapping.fmus,
            wrapper_inputs=sample_mapping.wrapper_inputs,
            wrapper_outputs=sample_mapping.wrapper_outputs,
            wrapper_parameters=sample_mapping.wrapper_parameters,
            reserved_parameters=build_reserved_parameters(sample_spec),
            connections=sample_mapping.connections,
            execution_order=sample_mapping.execution_order,
        )
        # Reserve the trailing value references (after user vars: in1=1, out1=2).
        for idx, mapped in enumerate(mapping.all_variables(), 1):
            mapped.wrapper_value_reference = idx
        return mapping

    def test_model_description_declares_knobs(self, sample_spec, reserved_mapping):
        xml = generate_model_description(sample_spec, reserved_mapping)
        root = ET.fromstring(xml)
        scalar_vars = list(root.find("ModelVariables").findall("ScalarVariable"))
        by_name = {sv.get("name"): sv for sv in scalar_vars}
        for knob in ("solver.type", "solver.tolerance", "solver.step_size"):
            sv = by_name[knob]
            assert sv.get("causality") == "parameter"
            assert sv.get("variability") == "fixed"
            assert sv.get("initial") == "exact"
        assert by_name["solver.type"].find("Integer").get("start") == "0"
        assert by_name["solver.tolerance"].find("Real").get("start") == "1e-06"
        assert by_name["solver.step_size"].find("Real").get("start") == "0.001"

    def test_interface_routes_knobs_to_solver_fields(self, sample_spec, reserved_mapping):
        content = generate_fmi_interface_impl(sample_spec, reserved_mapping)
        # Defaults set at instantiation.
        assert "inst->solver_type = 0;" in content
        assert "inst->solver_tolerance = 1e-06;" in content
        # Setter dispatch updates the WrapperInstance solver fields.
        assert "inst->solver_tolerance = value[i];" in content
        assert "inst->step_size = value[i];" in content
        assert "inst->solver_type = value[i];" in content
        # Getter dispatch reads them back.
        assert "value[i] = inst->solver_tolerance;" in content
        assert "value[i] = inst->solver_type;" in content

    def test_reserved_knobs_do_not_forward_to_internal_fmus(self, sample_spec, reserved_mapping):
        content = generate_fmi_interface_impl(sample_spec, reserved_mapping)
        # Reserved params are wrapper-local: their mapping carries no FMU,
        # so the C init wires them with fmu = NULL and the do-step loop never
        # forwards them to an internal FMU.
        assert "inst->real_params[0].fmu = NULL;" in content
        assert "inst->real_params[1].fmu = NULL;" in content
        assert "inst->int_params[0].fmu = NULL;" in content

    def test_variable_step_default(self, sample_spec, sample_mapping):
        from cs_fmu_packager.models import build_reserved_parameters
        spec = PackageSpec(
            metadata={"identifier": "test_fmu"},
            fmus=sample_spec.fmus,
            solver=SolverConfig(
                type="variable_step", step_size=0.001,
                communication_step=0.01, tolerance=1e-8,
            ),
            wrapper=WrapperConfig(communication_step=0.01),
        )
        mapping = MappingTable(
            fmus=sample_mapping.fmus,
            wrapper_inputs=sample_mapping.wrapper_inputs,
            wrapper_outputs=sample_mapping.wrapper_outputs,
            reserved_parameters=build_reserved_parameters(spec),
        )
        xml = generate_model_description(spec, mapping)
        root = ET.fromstring(xml)
        by_name = {
            sv.get("name"): sv
            for sv in root.find("ModelVariables").findall("ScalarVariable")
        }
        assert by_name["solver.type"].find("Integer").get("start") == "1"
        assert by_name["solver.tolerance"].find("Real").get("start") == "1e-08"
        content = generate_fmi_interface_impl(spec, mapping)
        assert "inst->solver_type = 1;" in content
        assert "inst->solver_tolerance = 1e-08;" in content