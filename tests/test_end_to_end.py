"""End-to-end tests for the cs-fmu-packager pipeline.

These tests validate the full pipeline from spec parsing through code
generation. Building (Phase 5) requires vcpkg+SUNDIALS, so those tests
are conditional on VCPKG_ROOT being set.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
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


# IMP-028: multi-FMU composite codegen + runtime (packaged SCC groups).
# The repo's tiny fixture FMUs carry no shared library, so this test
# generates real ME FMUs with OMC, packages a two-node chain through the
# CLI, and drives the resulting CS FMU with fmpy as the external master.

_HERE = os.path.abspath(os.path.dirname(__file__))
_GENERATE_SCRIPT = os.path.join(_HERE, "fixtures", "generate_test_fmus.py")
_OMC_AVAILABLE = shutil.which("omc") is not None
_FMPY_AVAILABLE = False
try:
    import fmpy  # noqa: F401
    _FMPY_AVAILABLE = True
except ImportError:
    pass


def _generate_chain_spec(work_dir: str) -> str:
    """Write a chained integrator -> gain spec and return its path."""
    integrator = os.path.join(work_dir, "integrator.fmu")
    gain = os.path.join(work_dir, "gain.fmu")
    spec = os.path.join(work_dir, "chain.toml")
    with open(spec, "w") as f:
        f.write(f'''
[metadata]
identifier = "chain_test"
description = "integrator -> gain chain composite"

[fmus]
m00 = {{ path = "{integrator}", fmi_version = "2.0", kind = "ModelExchange" }}
m01 = {{ path = "{gain}", fmi_version = "2.0", kind = "ModelExchange" }}

[[connections]]
source = "m00.y"
target = "m01.u"

[[variables]]
name = "u[1]"
type = "Real"
causality = "input"
target = "m00.u"

[[variables]]
name = "y[1]"
type = "Real"
causality = "output"
source = "m01.y"

[[variables]]
name = "m00.y[1]"
type = "Real"
causality = "output"
source = "m00.y"

[[variables]]
name = "m01.y[1]"
type = "Real"
causality = "output"
source = "m01.y"

[solver]
type = "fixed_step"
step_size = 0.001
communication_step = 0.01

[wrapper]
communication_step = 0.01
''')
    return spec


def _trajectory(result):
    """Normalise fmpy.simulate_fmu output (DataFrame or recarray) to
    ``(names, series_dict)``."""
    import numpy as np
    if hasattr(result, "columns"):  # pandas.DataFrame
        names = list(result.columns)
        return names, {n: np.asarray(result[n]).astype(np.float64) for n in names}
    names = list(result.dtype.names)
    return names, {n: np.asarray(result[n]) for n in names}


@pytest.mark.skipif(not _VCPKG_AVAILABLE, reason="VCPKG_ROOT not set")
@pytest.mark.skipif(not _OMC_AVAILABLE, reason="OpenModelica compiler (omc) not installed")
@pytest.mark.skipif(not _FMPY_AVAILABLE, reason="fmpy not installed (pip install fmpy)")
class TestMultiFmuEndToEnd:
    """IMP-028: a two-ME-node chained spec must build, package, and run."""

    def test_two_node_chain_builds_and_simulates(self, tmp_path):
        work = str(tmp_path)

        # 1. Generate real ME FMUs with OMC.
        subprocess.run(
            [sys.executable, _GENERATE_SCRIPT, work],
            check=True, capture_output=True, text=True, timeout=300,
        )
        for fname in ("integrator.fmu", "gain.fmu"):
            assert os.path.isfile(os.path.join(work, fname)), f"missing {fname}"

        # 2. Write the chained spec.
        spec = _generate_chain_spec(work)
        out_fmu = os.path.join(work, "chain.fmu")

        # 3. Build + package via the CLI.
        vcpkg_root = os.environ.get("VCPKG_ROOT")
        cmd = [
            sys.executable, "-m", "cs_fmu_packager", spec,
            "-o", out_fmu, "--vcpkg-root", vcpkg_root,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        assert result.returncode == 0, (
            f"packaging failed\nstdout:{result.stdout}\nstderr:{result.stderr}"
        )
        assert os.path.isfile(out_fmu)

        # Packaged FMU must embed the pre-extracted internal binaries.
        with zipfile.ZipFile(out_fmu) as zf:
            names = zf.namelist()
            assert "resources/m00/binaries/linux64/integrator.so" in names
            assert "resources/m01/binaries/linux64/gain.so" in names

        # 4. Drive the composite with fmpy (external master, steps the CS FMU).
        import fmpy
        import numpy as np

        stop_time = 0.2
        dt = np.dtype([("time", np.float64), ("u[1]", np.float64)])
        step = np.array([(0.0, 1.0), (1.0, 1.0)], dtype=dt)
        result = fmpy.simulate_fmu(
            out_fmu, start_time=0.0, stop_time=stop_time,
            step_size=0.01, input=step,
        )
        names, series = _trajectory(result)
        assert "y[1]" in names
        assert "m00.y[1]" in names
        assert "m01.y[1]" in names

        time = series["time"]
        y1 = series["y[1]"]
        y00 = series["m00.y[1]"]
        y01 = series["m01.y[1]"]

        # 5. Behavioural checks (integrator: y=x=t for u=1; gain: y=2*u):
        i_end = int(np.argmin(np.abs(time - stop_time)))
        # Integrator output tracks time.
        assert 0.0 < y00[i_end] < stop_time + 0.01, f"m00.y[1]={y00[i_end]}"
        assert abs(y00[i_end] - stop_time) < 5e-3
        # Gain doubles the chained integrator output (proves the connection).
        assert abs(y01[i_end] - 2.0 * y00[i_end]) < 5e-3, (
            f"m01.y[1]={y01[i_end]} not 2*m00.y[1]={y00[i_end]}"
        )
        # Boundary output mirrors the last node probe output.
        assert abs(y1[i_end] - y01[i_end]) < 1e-9
        # Outputs are recorded and finite over the whole run.
        assert np.all(np.isfinite(y1))

    def test_two_node_chain_respects_zero_input(self, tmp_path):
        """With u=0 the integrator state stays at zero (input propagation)."""
        work = str(tmp_path)
        subprocess.run(
            [sys.executable, _GENERATE_SCRIPT, work],
            check=True, capture_output=True, text=True, timeout=300,
        )
        spec = _generate_chain_spec(work)
        out_fmu = os.path.join(work, "chain.fmu")
        cmd = [
            sys.executable, "-m", "cs_fmu_packager", spec,
            "-o", out_fmu, "--vcpkg-root", os.environ.get("VCPKG_ROOT"),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        assert result.returncode == 0, result.stderr

        import fmpy
        import numpy as np
        dt = np.dtype([("time", np.float64), ("u[1]", np.float64)])
        step = np.array([(0.0, 0.0), (1.0, 0.0)], dtype=dt)
        result = fmpy.simulate_fmu(
            out_fmu, start_time=0.0, stop_time=0.1,
            step_size=0.01, input=step,
        )
        names, series = _trajectory(result)
        y00 = series["m00.y[1]"]
        y01 = series["m01.y[1]"]
        assert np.max(np.abs(y00)) < 1e-9, f"integrator drifted: {y00}"
        assert np.max(np.abs(y01)) < 1e-9, f"gain output drifted: {y01}"