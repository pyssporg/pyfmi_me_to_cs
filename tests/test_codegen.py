"""Tests for code generation (golden-file style)."""
from __future__ import annotations

import os
import tempfile

import pytest

from cs_fmu_packager.codegen.cmake import generate_cmake
from cs_fmu_packager.model_description import generate_model_description
from cs_fmu_packager.models import (
    FmuMetadata,
    FmuRef,
    MappingTable,
    MappedVariable,
    PackageSpec,
    ResolvedConnection,
    ScalarVariable,
    SolverConfig,
    WrapperConfig,
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
    return MappingTable(
        fmus={
            "src": FmuMetadata(
                fmi_version="2.0",
                guid="{src-guid}",
                model_name="SrcFMU",
                variables={
                    "u": ScalarVariable(name="u", value_reference=0, type="Real", causality="input"),
                    "y": ScalarVariable(name="y", value_reference=1, type="Real", causality="output"),
                },
            ),
            "tgt": FmuMetadata(
                fmi_version="2.0",
                guid="{tgt-guid}",
                model_name="TgtFMU",
                variables={
                    "u": ScalarVariable(name="u", value_reference=0, type="Real", causality="input"),
                    "y": ScalarVariable(name="y", value_reference=1, type="Real", causality="output"),
                },
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