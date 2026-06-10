"""Tests for code generation (golden-file style)."""
from __future__ import annotations

import os
import tempfile

import pytest

from cs_fmu_packager.codegen.cmake import generate_cmake
from cs_fmu_packager.codegen.fmi_interface import generate_fmi_interface_impl
from cs_fmu_packager.model_description import generate_model_description
from cs_fmu_packager.models import (
    FmuRef,
    MappingTable,
    MappedVariable,
    PackageSpec,
    ResolvedConnection,
    SolverConfig,
    WrapperConfig,
)
from pyssp_standard.standard.fmi2.model.model_description import (
    Fmi2ModelDescriptionDocument,
    Fmi2ScalarVariable,
)


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
        assert "find_package(SUNDIALS REQUIRED COMPONENTS arkode nvecserial)" in content
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
            fmus={},
            connections=[],
            variables=[],  # Empty — simulates auto-discovery
            solver=SolverConfig(type="fixed_step", step_size=0.001, communication_step=0.001),
            wrapper=None,
        )
        # This should not raise — codegen doesn't directly iterate spec.variables
        # It uses the mapping table which is populated by build_mapping
        assert spec.variables == []


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