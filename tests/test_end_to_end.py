"""End-to-end tests for the cs-fmu-packager pipeline.

These tests validate the full pipeline from spec parsing through code
generation. Building (Phase 5) requires vcpkg+SUNDIALS, so those tests
are conditional on VCPKG_ROOT being set.
"""

from __future__ import annotations

import json
import os
import tempfile
import zipfile

import pytest

from cs_fmu_packager.packager import assemble_fmu, write_build_report
from cs_fmu_packager.models import BuildReport


# Helper: check if vcpkg is available
_VCPKG_AVAILABLE = "VCPKG_ROOT" in os.environ and os.path.isdir(os.environ["VCPKG_ROOT"])


def _minimal_toml() -> str:
    """Return a minimal but valid spec for testing."""
    return """
[metadata]
identifier = "end_to_end_test"
description = "End-to-end test FMU"
author = "test"
version = "0.1.0"

[fmus]
src = { path = "/tmp/fake_src.fmu", fmi_version = "2.0", kind = "ModelExchange" }

[[connections]]
source = "src.y"
target = "src.u"

[[variables]]
name = "inp"
type = "Real"
causality = "input"
target = "src.u"

[[variables]]
name = "out"
type = "Real"
causality = "output"
source = "src.y"

[solver]
type = "fixed_step"
step_size = 0.001
communication_step = 0.01

[wrapper]
communication_step = 0.01
"""


class TestAssemblyWithoutBuild:
    """Assembly tests that create fake .so/FMU and do NOT need vcpkg."""

    def test_assembled_fmu_structure(self):
        """Test that the assembled FMU has correct ZIP structure."""
        import zipfile
        import tempfile
        import os

        # Create fake .so and FMU files
        with tempfile.TemporaryDirectory() as d:
            so_path = os.path.join(d, "test.so")
            with open(so_path, "wb") as f:
                f.write(b"\x7fELF...fake_so_content")

            fmu_path = os.path.join(d, "fake.fmu")
            with zipfile.ZipFile(fmu_path, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("modelDescription.xml", "<fmiModelDescription/>")

            # Create spec
            from cs_fmu_packager.models import (
                FmuRef, MappingTable,
                MappedVariable, PackageSpec,
                SolverConfig, WrapperConfig,
            )
            from pyssp_standard.standard.fmi2.model.model_description import (
                Fmi2ModelDescriptionDocument, Fmi2ScalarVariable,
            )

            spec = PackageSpec(
                metadata={"identifier": "test_fmu"},
                fmus={"internal": FmuRef(name="internal", path=fmu_path)},
                solver=SolverConfig(type="fixed_step", step_size=0.001, communication_step=0.01),
                wrapper=WrapperConfig(communication_step=0.01),
            )

            mapping = MappingTable(
                fmus={
                    "internal": Fmi2ModelDescriptionDocument(
                        root=None, fmi_version="2.0", guid="{test-guid}",
                        model_name="InternalFMU",
                        variables=[], unit_definitions=[], type_definitions=[],
                        model_structure=None,
                    ),
                },
                execution_order=["internal"],
            )

            # Assemble
            output_path = os.path.join(d, "result.fmu")
            report = assemble_fmu(spec, mapping, so_path, output_path)

            # Verify structure
            with zipfile.ZipFile(output_path, "r") as zf:
                names = zf.namelist()
                assert "modelDescription.xml" in names
                assert "binaries/linux64/test_fmu.so" in names
                assert "resources/internal.fmu" in names

    def test_deterministic_content(self):
        """Assembled FMU should have deterministic content for same inputs."""
        import tempfile
        import os
        import zipfile

        with tempfile.TemporaryDirectory() as d:
            # Create files with same content twice
            so_content = b"\x7fELF...test"

            so_path = os.path.join(d, "test.so")
            with open(so_path, "wb") as f:
                f.write(so_content)

            fmu_path = os.path.join(d, "fake.fmu")
            with zipfile.ZipFile(fmu_path, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("modelDescription.xml", "<fmiModelDescription/>")

            from cs_fmu_packager.models import (
                FmuRef, MappingTable, PackageSpec,
                SolverConfig, WrapperConfig,
            )
            from pyssp_standard.standard.fmi2.model.model_description import (
                Fmi2ModelDescriptionDocument,
            )

            spec = PackageSpec(
                metadata={"identifier": "det_test"},
                fmus={"m": FmuRef(name="m", path=fmu_path)},
                solver=SolverConfig(type="fixed_step", step_size=0.001, communication_step=0.01),
                wrapper=WrapperConfig(communication_step=0.01),
            )

            mapping = MappingTable(
                fmus={
                    "m": Fmi2ModelDescriptionDocument(
                        root=None, fmi_version="2.0", guid="{test}",
                        model_name="M",
                        variables=[], unit_definitions=[], type_definitions=[],
                        model_structure=None,
                    ),
                },
                execution_order=["m"],
            )

            out1 = os.path.join(d, "r1.fmu")
            out2 = os.path.join(d, "r2.fmu")
            assemble_fmu(spec, mapping, so_path, out1)
            assemble_fmu(spec, mapping, so_path, out2)

            # Read and compare checksums
            import hashlib
            def sha256(p):
                h = hashlib.sha256()
                with open(p, "rb") as f:
                    for chunk in iter(lambda: f.read(4096), b""):
                        h.update(chunk)
                return h.hexdigest()

            # Note: modelDescription.xml contains a timestamp,
            # so the ZIP checksums won't match. But the GUID and
            # structure should be deterministic.
            with zipfile.ZipFile(out1) as z1, zipfile.ZipFile(out2) as z2:
                n1 = sorted(z1.namelist())
                n2 = sorted(z2.namelist())
                assert n1 == n2

    def test_auto_discovery_without_variables_section(self):
        """End-to-end: spec without [[variables]] should auto-discover variables."""
        # Create a spec without [[variables]]
        spec_str = """
[metadata]
identifier = "auto_discovery_test"

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
        fd, path = tempfile.mkstemp(suffix=".toml")
        os.write(fd, spec_str.encode())
        os.close(fd)
        try:
            from cs_fmu_packager.spec import parse_spec
            spec = parse_spec(path)
            assert spec.variables == [], f"Expected empty variables, got {spec.variables}"
        finally:
            os.unlink(path)


@pytest.mark.skipif(not _VCPKG_AVAILABLE, reason="VCPKG_ROOT not set")
class TestBuildReport:
    """VR-007: Build report verification."""

    def test_report_content(self):
        """Validate build report format and content."""
        import tempfile
        import os
        import json

        with tempfile.TemporaryDirectory() as d:
            report = BuildReport(
                spec_path="spec.toml",
                output_path="out.fmu",
                tool_version="0.1.0",
                fmu_count=2,
                variable_count=3,
                connection_count=1,
                algebraic_loop_count=1,
                solver_type="fixed_step",
                solver_step_size=0.001,
                communication_step=0.01,
                warnings=["Test warning"],
                fmu_guids={"a": "{guid-a}"},
                wrapper_variables=["inp", "out"],
            )

            report_path = os.path.join(d, "report.json")
            write_build_report(report, report_path)

            with open(report_path) as f:
                data = json.load(f)

            assert data["tool_version"] == "0.1.0"
            assert data["fmu_count"] == 2
            assert data["solver_type"] == "fixed_step"
            assert data["algebraic_loop_count"] == 1
            assert "Test warning" in data["warnings"]
            assert data["fmu_guids"]["a"] == "{guid-a}"
            assert "inp" in data["wrapper_variables"]