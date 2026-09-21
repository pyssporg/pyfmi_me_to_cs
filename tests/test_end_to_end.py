"""End-to-end tests for the cs-fmu-packager pipeline.

These tests validate the full pipeline from spec parsing through code
generation. Building (Phase 5) requires vcpkg+SUNDIALS, so those tests
are conditional on VCPKG_ROOT being set.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime

import pytest

from cs_fmu_packager.packager import assemble_fmu, write_build_report
from cs_fmu_packager.models import BuildReport


# Helper: check if vcpkg is available
_VCPKG_AVAILABLE = "VCPKG_ROOT" in os.environ and os.path.isdir(os.environ["VCPKG_ROOT"])


def _make_simple_ssp(work_dir: str, *, connectors: list[dict], fmu_names=None):
    """Write a small .ssp archive (two fake FMUs) and return its path (IMP-029)."""
    from tests.helpers import build_ssp_document
    from pyssp_standard.standard.ssp1.codec.ssd_codec import Ssp1SsdCodec

    fmu_names = fmu_names or ["src.fmu", "tgt.fmu"]
    fmu_sources = {
        "src": f"resources/{fmu_names[0]}",
        "tgt": f"resources/{fmu_names[1]}",
    }
    document = build_ssp_document(
        name="auto_discovery_test",
        fmu_sources=fmu_sources,
        connectors=connectors,
    )
    ssp_path = os.path.join(work_dir, "spec.ssp")
    with zipfile.ZipFile(ssp_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("SystemStructure.ssd", Ssp1SsdCodec().serialize(document))
        for member in fmu_sources.values():
            zf.writestr(member, b"fake-fmu")
    return ssp_path


def _zip_with_variables() -> bytes:
    """Return bytes of a minimal FMU whose modelDescription exposes
    ``u`` (input), ``y`` (output) and ``p`` (parameter) scalar variables."""
    import io

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<fmiModelDescription fmiVersion="2.0" modelName="m00" '
        'guid="{auto-guid}" generationTool="test" numberOfEventIndicators="0">\n'
        '  <ModelExchange modelIdentifier="m00" />\n'
        "  <ModelVariables>\n"
        '    <ScalarVariable name="u" valueReference="0" causality="input">'
        '<Real start="0.0"/></ScalarVariable>\n'
        '    <ScalarVariable name="y" valueReference="1" causality="output">'
        "<Real/></ScalarVariable>\n"
        '    <ScalarVariable name="p" valueReference="2" causality="parameter">'
        '<Real start="3.0"/></ScalarVariable>\n'
        "  </ModelVariables>\n"
        "</fmiModelDescription>\n"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("modelDescription.xml", xml)
    return buf.getvalue()


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
                SolverConfig, WrapperConfig, WrapperVariable,
            )
            from pyssp_standard.standard.fmi2.model.model_description import (
                Fmi2ModelDescriptionDocument,
            )

            spec = PackageSpec(
                metadata={"identifier": "test_fmu"},
                fmus={"internal": FmuRef(name="internal", path=fmu_path)},
                variables=[
                    WrapperVariable(
                        name="u", type="Real", causality="input",
                        target_fmu="internal", target_variable="u",
                    ),
                ],
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
                wrapper_inputs=[
                    MappedVariable(
                        wrapper_name="u", variable_type="Real", causality="input",
                        wrapper_value_reference=1, target_fmu="internal",
                        target_variable="u", target_value_reference=0,
                    ),
                ],
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

    def test_assembled_fmu_structure_with_date_time(self):
        """The ``date_time`` (pyssp) assembly path yields the same FMU structure.

        Experiment result: pyssp_standard does NOT propagate ``date_time`` to
        the ZIP entry timestamps (every entry carries the FMI_EPOCH fixed
        timestamp ``2000-01-01 00:00:00``); instead it writes the datetime
        into the ``generationDateAndTime`` attribute of modelDescription.xml.
        We therefore assert the structure and that attribute.
        """
        import tempfile
        import os
        import zipfile

        with tempfile.TemporaryDirectory() as d:
            so_path = os.path.join(d, "test.so")
            with open(so_path, "wb") as f:
                f.write(b"\x7fELF...fake_so_content")

            fmu_path = os.path.join(d, "fake.fmu")
            with zipfile.ZipFile(fmu_path, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("modelDescription.xml", "<fmiModelDescription/>")

            from cs_fmu_packager.models import (
                FmuRef, MappingTable,
                MappedVariable, PackageSpec,
                SolverConfig, WrapperConfig, WrapperVariable,
            )
            from pyssp_standard.standard.fmi2.model.model_description import (
                Fmi2ModelDescriptionDocument,
            )

            spec = PackageSpec(
                metadata={"identifier": "test_fmu"},
                fmus={"internal": FmuRef(name="internal", path=fmu_path)},
                variables=[
                    WrapperVariable(
                        name="u", type="Real", causality="input",
                        target_fmu="internal", target_variable="u",
                    ),
                ],
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
                wrapper_inputs=[
                    MappedVariable(
                        wrapper_name="u", variable_type="Real", causality="input",
                        wrapper_value_reference=1, target_fmu="internal",
                        target_variable="u", target_value_reference=0,
                    ),
                ],
                execution_order=["internal"],
            )

            # Assemble via the pyssp (date_time) pathway
            output_path = os.path.join(d, "result.fmu")
            assemble_fmu(
                spec, mapping, so_path, output_path, date_time=datetime(2024, 1, 1),
            )

            with zipfile.ZipFile(output_path, "r") as zf:
                names = zf.namelist()
                assert "modelDescription.xml" in names
                assert "binaries/linux64/test_fmu.so" in names
                assert "resources/internal.fmu" in names

                md = zf.read("modelDescription.xml").decode("utf-8")
                assert "generationDateAndTime=\"2024-01-01T00:00:00Z\"" in md, md

    def test_deterministic_content(self):
        """Assembled FMU should have deterministic content for same inputs."""
        import tempfile
        import os
        import zipfile
        import re

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

            with zipfile.ZipFile(out1) as z1, zipfile.ZipFile(out2) as z2:
                n1 = sorted(z1.namelist())
                n2 = sorted(z2.namelist())
                assert n1 == n2

                for name in n1:
                    b1 = z1.read(name)
                    b2 = z2.read(name)
                    if name == "modelDescription.xml":
                        # modelDescription.xml is regenerated per call with a
                        # fresh generationDateAndTime timestamp; normalize it.
                        s1 = re.sub(r'generationDateAndTime="[^"]*"', "", b1.decode("utf-8"))
                        s2 = re.sub(r'generationDateAndTime="[^"]*"', "", b2.decode("utf-8"))
                        assert s1 == s2, f"modelDescription.xml differs beyond timestamp"
                    else:
                        assert b1 == b2, f"member '{name}' differs between runs"

                # Embedded internal FMU member must be byte-identical too.
                assert z1.read("resources/m.fmu") == z2.read("resources/m.fmu")

    def test_auto_discovery_from_fmu_variables(self, tmp_path, make_ssp):
        """Auto-discovery is owned by the mapper: a connector-less .ssp whose
        FMUs expose variables yields wrapper variables via ``build_mapping``."""
        from cs_fmu_packager.ssp_spec import parse_spec
        from cs_fmu_packager.mapper import build_mapping

        spec_path = make_ssp(
            fmu_sources={"m00": "resources/m00.fmu"},
            fmu_files={"m00": _zip_with_variables()},
            connectors=[],
            name="auto_discovery",
        )
        spec = parse_spec(spec_path, workspace_dir=str(tmp_path / "ws"))
        assert spec.variables == [], (
            f"parse_spec must NOT auto-discover; the mapper owns that. Got {spec.variables}"
        )

        mapping = build_mapping(spec)
        variables = mapping.all_variables()
        by_name = {v.wrapper_name: v for v in variables}
        assert set(by_name) == {
            "u", "y", "p",
            "solver.type", "solver.tolerance", "solver.step_size",
        }, f"discovered: {sorted(by_name)}"
        assert by_name["u"].causality == "input"
        assert by_name["y"].causality == "output"
        assert by_name["p"].causality == "parameter"
        refs = [v.wrapper_value_reference for v in variables]
        assert refs == list(range(1, len(refs) + 1)), f"refs: {refs}"


class TestBuildReportSerialization:
    """JSON build-report serialization (runs everywhere, no vcpkg needed)."""

    def test_report_content(self):
        """Validate build report format and content."""
        import tempfile
        import os
        import json

        with tempfile.TemporaryDirectory() as d:
            report = BuildReport(
                spec_path="spec.ssp",
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


class TestCliPipeline:
    """CLI ``_execute``/click pipeline tests (heavy build monkeypatched)."""

    def _make_ssp(self, make_ssp) -> str:
        return make_ssp(fmu_sources={"m00": "resources/m00.fmu"})

    def _install_fake_build(self, monkeypatch, so_path):
        import cs_fmu_packager.cli as cli_mod
        from cs_fmu_packager.builder import BuildResult

        def fake_build_fmu(*args, **kwargs):
            return BuildResult(
                success=True, so_path=so_path, tool_versions={"python": "3.x"},
            )

        monkeypatch.setattr(cli_mod, "build_fmu", fake_build_fmu)
        return cli_mod

    def _install_recording_assemble(self, monkeypatch, cli_mod, captured, report):
        def fake_assemble_fmu(**kwargs):
            captured["spec"] = kwargs["spec"]
            captured["mapping"] = kwargs["mapping"]
            return report

        monkeypatch.setattr(cli_mod, "assemble_fmu", fake_assemble_fmu)

    def test_dry_run_creates_no_output(self, tmp_path, make_ssp):
        """``--dry-run`` validates + inspects but creates no FMU file."""
        import click
        from click.testing import CliRunner
        import cs_fmu_packager.cli as cli_mod

        spec_path = self._make_ssp(make_ssp)
        out_fmu = os.path.join(str(tmp_path), "must_not_exist.fmu")
        result = CliRunner().invoke(
            cli_mod.main, [spec_path, "--dry-run", "-o", out_fmu],
        )
        assert result.exit_code == 0, result.output
        assert "Dry run:" in result.output
        assert not os.path.exists(out_fmu)

    def test_dry_run_missing_spec_fails(self):
        """A nonexistent spec path must fail with a click validation error."""
        from click.testing import CliRunner
        import cs_fmu_packager.cli as cli_mod

        result = CliRunner().invoke(cli_mod.main, ["nope.ssp", "--dry-run"])
        assert result.exit_code != 0
        assert "Error:" in result.output

    def test_step_size_override_propagates(self, tmp_path, make_ssp, monkeypatch):
        """``_execute`` overrides must reach the spec handed to assembly."""
        import cs_fmu_packager.cli as cli_mod
        from cs_fmu_packager.models import BuildReport

        spec_path = self._make_ssp(make_ssp)
        so_path = os.path.join(str(tmp_path), "fake.so")
        with open(so_path, "wb") as f:
            f.write(b"\x7fELF")

        cli_mod = self._install_fake_build(monkeypatch, so_path)
        captured = {}
        self._install_recording_assemble(
            monkeypatch, cli_mod, captured,
            BuildReport(
                spec_path="x.ssp", output_path="x.fmu", tool_version="0.1.0",
                fmu_count=1, variable_count=0, connection_count=0,
                algebraic_loop_count=0, solver_type="fixed_step",
                solver_step_size=0.0005, communication_step=0.001,
            ),
        )

        out_fmu = os.path.join(str(tmp_path), "out.fmu")
        cli_mod._execute(
            spec_path, out_fmu, None, None, None,
            dry_run=False, step_size=0.0005, communication_step=0.001,
            verbose=False,
        )
        assert captured["spec"].solver.step_size == 0.0005
        assert captured["spec"].wrapper.communication_step == 0.001

    def test_invalid_step_sizes_raise(self, make_ssp, tmp_path):
        """``_execute`` must reject non-positive or inverted step sizes."""
        import cs_fmu_packager.cli as cli_mod
        from cs_fmu_packager.errors import SpecValidationError

        spec_path = self._make_ssp(make_ssp)
        for step_size, comm_step in ((0.0, 0.01), (0.1, 0.01)):
            with pytest.raises(SpecValidationError):
                cli_mod._execute(
                    spec_path, None, None, None, None,
                    dry_run=False, step_size=step_size,
                    communication_step=comm_step, verbose=False,
                )

    def test_report_json_written(self, tmp_path, make_ssp, monkeypatch):
        """``--report`` writes a parseable JSON build report."""
        import cs_fmu_packager.cli as cli_mod
        from cs_fmu_packager.models import BuildReport

        spec_path = self._make_ssp(make_ssp)
        so_path = os.path.join(str(tmp_path), "fake.so")
        with open(so_path, "wb") as f:
            f.write(b"\x7fELF")

        report = BuildReport(
            spec_path="spec.ssp", output_path="out.fmu", tool_version="0.1.0",
            fmu_count=1, variable_count=2, connection_count=0,
            algebraic_loop_count=0, solver_type="fixed_step",
            solver_step_size=0.001, communication_step=0.01,
            warnings=["w1"], fmu_guids={"m00": "{guid}"},
            wrapper_variables=["u"],
        )
        cli_mod = self._install_fake_build(monkeypatch, so_path)
        captured = {}
        self._install_recording_assemble(monkeypatch, cli_mod, captured, report)

        out_fmu = os.path.join(str(tmp_path), "out.fmu")
        report_path = os.path.join(str(tmp_path), "report.json")
        cli_mod._execute(
            spec_path, out_fmu, report_path, None, None,
            dry_run=False, step_size=None, communication_step=None,
            verbose=False,
        )
        assert os.path.isfile(report_path)
        with open(report_path) as f:
            data = json.load(f)
        assert data["tool_version"] == "0.1.0"
        assert data["variable_count"] == 2
        assert data["fmu_guids"]["m00"] == "{guid}"
        assert data["wrapper_variables"] == ["u"]

    def test_click_smoke_dry_run_options(self, make_ssp):
        """Full click option parsing smoke test (dry run, all options)."""
        from click.testing import CliRunner
        import cs_fmu_packager.cli as cli_mod

        spec_path = self._make_ssp(make_ssp)
        result = CliRunner().invoke(
            cli_mod.main,
            [spec_path, "--dry-run", "-o", "x.fmu", "--step-size", "0.001"],
        )
        assert result.exit_code == 0, result.output


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


def _generate_chain_ssp(
    work_dir: str,
    *,
    input_name: str = "u[1]",
    output_name: str = "y[1]",
    m00_output_name: str = "m00.y[1]",
    m01_output_name: str = "m01.y[1]",
) -> str:
    """Write a complete ``chain.ssp`` archive (integrator -> gain) and return its path.

    Boundary connector names are parameterizable so tests can expose the
    interface as ``u``/``y`` (matching an OMC reference FMU) or the original
    ``u[1]``/``y[1]`` defaults.
    """
    from xml.etree import ElementTree as ET

    from tests.helpers import build_ssp_document
    from pyssp_standard.standard.ssp1.codec.ssd_codec import Ssp1SsdCodec

    integrator = os.path.join(work_dir, "integrator.fmu")
    gain = os.path.join(work_dir, "gain.fmu")
    ssp_path = os.path.join(work_dir, "chain.ssp")

    solver = ET.Element("Solver")
    solver.set("type", "fixed_step")
    solver.set("stepSize", "0.001")
    solver.set("communicationStep", "0.01")
    wrapper = ET.Element("Wrapper")
    wrapper.set("communicationStep", "0.01")

    document = build_ssp_document(
        name="chain_test",
        fmu_sources={
            "m00": "resources/integrator.fmu",
            "m01": "resources/gain.fmu",
        },
        connectors=[
            {"element": "m00/u", "name": input_name, "kind": "input", "type_name": "Real"},
            {"element": "m01/y", "name": output_name, "kind": "output", "type_name": "Real"},
            {"element": "m00/y", "name": m00_output_name, "kind": "output", "type_name": "Real"},
            {"element": "m01/y", "name": m01_output_name, "kind": "output", "type_name": "Real"},
        ],
        connections=[("m00", "y", "m01", "u")],
        annotations=[("cs-fmu-packager", [solver, wrapper])],
    )
    with zipfile.ZipFile(ssp_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("SystemStructure.ssd", Ssp1SsdCodec().serialize(document))
        for member, fmu in (
            ("resources/integrator.fmu", integrator),
            ("resources/gain.fmu", gain),
        ):
            with open(fmu, "rb") as f:
                zf.writestr(member, f.read())
    return ssp_path


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

    def test_two_node_chain_builds_and_simulates(self, artifact_dir):
        work = str(artifact_dir)

        # 1. Generate real ME FMUs with OMC.
        subprocess.run(
            [sys.executable, _GENERATE_SCRIPT, work],
            check=True, capture_output=True, text=True, timeout=300,
        )
        for fname in ("integrator.fmu", "gain.fmu"):
            assert os.path.isfile(os.path.join(work, fname)), f"missing {fname}"

        # 2. Write the chained .ssp package.
        ssp = _generate_chain_ssp(work)
        out_fmu = os.path.join(work, "chain.fmu")

        # 3. Build + package via the CLI.
        vcpkg_root = os.environ.get("VCPKG_ROOT")
        cmd = [
            sys.executable, "-m", "cs_fmu_packager", ssp,
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

    def test_two_node_chain_respects_zero_input(self, artifact_dir):
        """With u=0 the integrator state stays at zero (input propagation)."""
        work = str(artifact_dir)
        subprocess.run(
            [sys.executable, _GENERATE_SCRIPT, work],
            check=True, capture_output=True, text=True, timeout=300,
        )
        ssp = _generate_chain_ssp(work)
        out_fmu = os.path.join(work, "chain.fmu")
        cmd = [
            sys.executable, "-m", "cs_fmu_packager", ssp,
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

    def test_packager_matches_omc_reference(self, artifact_dir):
        """Packager artifact and OMC reference CS FMU agree on ``y`` (u=1 step)."""
        work = str(artifact_dir)

        subprocess.run(
            [sys.executable, _GENERATE_SCRIPT, work, "--cs"],
            check=True, capture_output=True, text=True, timeout=300,
        )
        for fname in ("integrator.fmu", "gain.fmu", "IntegratorWithGain_CS.fmu"):
            assert os.path.isfile(os.path.join(work, fname)), f"missing {fname}"

        # Boundary connectors named exactly u / y so the reference and the
        # artifact expose the same interface.
        ssp = _generate_chain_ssp(work, input_name="u", output_name="y")
        out_fmu = os.path.join(work, "IntegratorWithGain.fmu")
        cmd = [
            sys.executable, "-m", "cs_fmu_packager", ssp,
            "-o", out_fmu, "--vcpkg-root", os.environ.get("VCPKG_ROOT"),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        assert result.returncode == 0, (
            f"packaging failed\nstdout:{result.stdout}\nstderr:{result.stderr}"
        )
        assert os.path.isfile(out_fmu)

        reference_dir = os.path.join(work, "reference")
        packager_dir = os.path.join(work, "packager")
        os.makedirs(reference_dir, exist_ok=True)
        os.makedirs(packager_dir, exist_ok=True)
        shutil.copy2(
            os.path.join(work, "IntegratorWithGain_CS.fmu"),
            os.path.join(reference_dir, "IntegratorWithGain_CS.fmu"),
        )
        shutil.copy2(out_fmu, os.path.join(packager_dir, "IntegratorWithGain.fmu"))

        import numpy as np
        from tests.fixtures.cs_verification import verify_cs_behavior

        stop_time = 1.0
        dt = np.dtype([("time", np.float64), ("u", np.float64)])
        input_signal = np.array(
            [(0.0, 0.0), (0.0, 1.0), (stop_time, 1.0)], dtype=dt,
        )

        ver = verify_cs_behavior(
            compound_name="IntegratorWithGain",
            reference_cs_dir=reference_dir,
            packager_output_dir=packager_dir,
            start_time=0.0,
            stop_time=stop_time,
            step_size=0.01,
            rtol=1e-2,
            atol=5e-3,
            input_signal=input_signal,
        )

        if not ver["passed"]:
            ref = ver["reference_trajectory"]
            art = ver["artifact_trajectory"]
            print("\n=== REFERENCE vs PACKAGER DIAGNOSTICS ===")
            print("common columns:", sorted(set(ref.columns) & set(art.columns)))
            print("reference columns:", list(ref.columns))
            print("artifact columns:", list(art.columns))
            print("max_deviations:", ver["max_deviations"])
            print("max_relative_deviations:", ver["max_relative_deviations"])
            print("reference tail:\n", ref.tail())
            print("artifact tail:\n", art.tail())

        assert ver["passed"], (
            "packager trajectory deviates from OMC reference: "
            f"{ver['max_deviations']}"
        )
        assert "y" in ver["max_deviations"], (
            f"'y' missing from compared variables: {sorted(ver['max_deviations'])}"
        )
        assert ver["max_deviations"]["y"] < 5e-3, (
            f"max |y_ref - y_art| = {ver['max_deviations']['y']}"
        )
