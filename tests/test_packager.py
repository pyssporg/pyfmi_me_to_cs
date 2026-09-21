"""Unit tests for FMU assembly / packaging (packager.py).

Focuses on the error paths and the inner-FMU runtime-payload embedding
behaviour that the happy-path integration tests do not cover.
"""
from __future__ import annotations

import os
import zipfile

import pytest

from cs_fmu_packager.errors import PackagingError
from cs_fmu_packager.models import FmuRef, MappingTable, PackageSpec
from cs_fmu_packager.packager import (
    _assemble_fmu_via_pyssp,
    _inner_model_identifier,
    _iter_inner_fmu_runtime_files,
    _model_identifier_for,
    assemble_fmu,
    write_build_report,
)
from pyssp_standard.standard.fmi2.model.model_description import (
    Fmi2ModelDescriptionDocument,
)


def _make_inner_fmu(path: str, model_identifier: str, *, bad_zip: bool = False):
    """Write a minimal inner ME FMU with a fake shared library."""
    if bad_zip:
        with open(path, "wb") as f:
            f.write(b"this is not a zip")
        return
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<fmiModelDescription fmiVersion="2.0" modelName="inner" guid="{g}">\n'
        f'  <ModelExchange modelIdentifier="{model_identifier}" />\n'
        "  <ModelVariables/>\n"
        "</fmiModelDescription>\n"
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("modelDescription.xml", xml)
        zf.writestr("binaries/linux64/inner_model.so", b"\x7fELF-fake-so")
        zf.writestr("resources/data.txt", b"payload")


def _spec_and_mapping(inner_path: str, fmu_id: str = "inner") -> tuple[PackageSpec, MappingTable]:
    spec = PackageSpec(
        metadata={"identifier": "out_fmu"},
        fmus={fmu_id: FmuRef(name=fmu_id, path=inner_path)},
        variables=[],
    )
    doc = Fmi2ModelDescriptionDocument(
        root=None, fmi_version="2.0", guid="{g}", model_name="inner",
        variables=[], unit_definitions=[], type_definitions=[],
        model_structure=None,
        capabilities=None,
    )
    mapping = MappingTable(fmus={fmu_id: doc})
    return spec, mapping


class TestAssembleFmuErrors:
    def test_missing_so_raises(self, tmp_path):
        inner = tmp_path / "inner.fmu"
        _make_inner_fmu(str(inner), "inner_model")
        spec, mapping = _spec_and_mapping(str(inner))
        with pytest.raises(PackagingError) as exc:
            assemble_fmu(
                spec, mapping,
                so_path=str(tmp_path / "missing.so"),
                output_path=str(tmp_path / "out.fmu"),
            )
        assert "not found" in str(exc.value)

    def test_missing_internal_fmu_raises(self, tmp_path):
        spec, mapping = _spec_and_mapping(str(tmp_path / "nope.fmu"))
        so_path = tmp_path / "x.so"
        so_path.write_bytes(b"\x7fELF")
        with pytest.raises(PackagingError) as exc:
            assemble_fmu(
                spec, mapping,
                so_path=str(so_path),
                output_path=str(tmp_path / "out.fmu"),
            )
        assert "not found" in str(exc.value)
        assert "nope.fmu" in str(exc.value)

    def test_invalid_inner_fmu_zip_raises(self, tmp_path):
        inner = tmp_path / "bad.fmu"
        _make_inner_fmu(str(inner), "inner_model", bad_zip=True)
        spec, mapping = _spec_and_mapping(str(inner))
        so_path = tmp_path / "x.so"
        so_path.write_bytes(b"\x7fELF")
        with pytest.raises(PackagingError) as exc:
            assemble_fmu(
                spec, mapping,
                so_path=str(so_path),
                output_path=str(tmp_path / "out.fmu"),
            )
        assert "not a valid ZIP archive" in str(exc.value)


class TestIterInnerFmuRuntimeFiles:
    def test_renames_binary_to_model_identifier(self, tmp_path):
        inner = tmp_path / "inner.fmu"
        _make_inner_fmu(str(inner), "custom_id")
        names = [name for name, _ in _iter_inner_fmu_runtime_files(str(inner), "custom_id")]
        assert "binaries/linux64/custom_id.so" in names
        assert "binaries/linux64/inner_model.so" not in names
        assert "resources/data.txt" in names

    def test_falls_back_to_parsed_model_identifier(self, tmp_path):
        inner = tmp_path / "inner.fmu"
        _make_inner_fmu(str(inner), "parsed_id")
        names = [name for name, _ in _iter_inner_fmu_runtime_files(str(inner))]
        assert "binaries/linux64/parsed_id.so" in names

    def test_non_linux_binary_left_alone(self, tmp_path):
        inner = tmp_path / "inner.fmu"
        _make_inner_fmu(str(inner), "parsed_id")
        with zipfile.ZipFile(inner, "a") as zf:
            zf.writestr("binaries/win64/inner_model.dll", b"fake")
        names = [name for name, _ in _iter_inner_fmu_runtime_files(str(inner))]
        assert "binaries/win64/inner_model.dll" in names


class TestInnerModelIdentifier:
    def test_returns_model_identifier(self, tmp_path):
        inner = tmp_path / "inner.fmu"
        _make_inner_fmu(str(inner), "my_id")
        assert _inner_model_identifier(str(inner)) == "my_id"

    def test_none_when_xml_has_no_identifier(self, tmp_path):
        inner = tmp_path / "inner.fmu"
        with zipfile.ZipFile(inner, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("modelDescription.xml", "<fmiModelDescription/>")
        assert _inner_model_identifier(str(inner)) is None

    def test_none_when_not_a_zip(self, tmp_path):
        inner = tmp_path / "inner.fmu"
        inner.write_bytes(b"garbage")
        assert _inner_model_identifier(str(inner)) is None


class TestModelIdentifierFor:
    def test_returns_none_without_capabilities(self):
        doc = Fmi2ModelDescriptionDocument(
            root=None, fmi_version="2.0", guid="{g}", model_name="m",
            variables=[], unit_definitions=[], type_definitions=[],
            model_structure=None, capabilities=None,
        )
        mapping = MappingTable(fmus={"m": doc})
        assert _model_identifier_for(mapping, "m") is None

    def test_returns_identifier_from_capabilities(self):
        from pyssp_standard.standard.fmi2.model.model_description import (
            Fmi2InterfaceAttributes,
        )
        doc = Fmi2ModelDescriptionDocument(
            root=None, fmi_version="2.0", guid="{g}", model_name="m",
            variables=[], unit_definitions=[], type_definitions=[],
            model_structure=None,
            capabilities=Fmi2InterfaceAttributes(model_identifier="cap_id"),
        )
        mapping = MappingTable(fmus={"m": doc})
        assert _model_identifier_for(mapping, "m") == "cap_id"


class TestWriteBuildReport:
    def test_write_failure_raises(self, tmp_path, monkeypatch):
        from cs_fmu_packager.models import BuildReport

        report = BuildReport(
            spec_path="s", output_path="o", tool_version="0.1.0",
            fmu_count=1, variable_count=0, connection_count=0,
            algebraic_loop_count=0, solver_type="fixed_step",
            solver_step_size=0.001, communication_step=0.001,
        )

        def _raise_open(*args, **kwargs):
            raise OSError("disk full")

        monkeypatch.setattr("builtins.open", _raise_open)
        with pytest.raises(PackagingError) as exc:
            write_build_report(report, str(tmp_path / "report.json"))
        assert "Failed to write build report" in str(exc.value)


class TestAssembleReportContent:
    def test_report_reflects_mapping(self, tmp_path):
        inner = tmp_path / "inner.fmu"
        _make_inner_fmu(str(inner), "inner_model")
        so_path = tmp_path / "x.so"
        so_path.write_bytes(b"\x7fELF")
        spec, mapping = _spec_and_mapping(str(inner))
        report = assemble_fmu(
            spec, mapping,
            so_path=str(so_path),
            output_path=str(tmp_path / "out.fmu"),
        )
        assert report.fmu_count == 1
        assert report.fmu_guids == {"inner": "{g}"}
        assert report.solver_type == "fixed_step"

        with zipfile.ZipFile(str(tmp_path / "out.fmu")) as zf:
            names = zf.namelist()
            assert "modelDescription.xml" in names
            assert "binaries/linux64/out_fmu.so" in names
            assert "resources/inner.fmu" in names
            # IMP-028 runtime payload pre-extracted
            assert "resources/inner/binaries/linux64/inner_model.so" in names