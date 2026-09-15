"""Tests for SSP package parsing and normalization (IMP-029)."""
from __future__ import annotations

import os
import zipfile
from xml.etree import ElementTree as ET

import pytest

from cs_fmu_packager.errors import SpecValidationError
from cs_fmu_packager.ssp_spec import parse_spec


def _connectors_for_two_fmus():
    return [
        {"element": "src/u", "name": "input1", "kind": "input", "type_name": "Real"},
        {"element": "tgt/y", "name": "output1", "kind": "output", "type_name": "Real"},
    ]


def _valid_fmu_sources():
    return {
        "src": "resources/src.fmu",
        "tgt": "resources/tgt.fmu",
    }


class TestSspParsing:
    """Valid complete .ssp packages normalize to PackageSpec."""

    def test_valid_ssp_parses(self, make_ssp, tmp_path):
        ssp_path = make_ssp(
            fmu_sources=_valid_fmu_sources(),
            connectors=_connectors_for_two_fmus(),
            connections=[("src", "y", "tgt", "u")],
            name="test_sys",
        )
        spec = parse_spec(ssp_path, workspace_dir=str(tmp_path))
        assert spec.metadata["identifier"] == "test_sys"
        assert set(spec.fmus) == {"src", "tgt"}
        assert len(spec.connections) == 1
        assert spec.connections[0].source_fmu == "src"
        assert spec.connections[0].source_variable == "y"
        assert spec.connections[0].target_fmu == "tgt"
        assert spec.connections[0].target_variable == "u"
        assert len(spec.variables) == 2
        assert spec.variables[0].causality == "input"
        assert spec.variables[0].target_fmu == "src"
        assert spec.variables[0].target_variable == "u"
        assert spec.variables[1].causality == "output"
        assert spec.variables[1].source_fmu == "tgt"
        assert spec.variables[1].source_variable == "y"
        # Defaults apply without a vendor annotation.
        assert spec.solver.type == "fixed_step"
        assert spec.solver.step_size == 0.001
        assert spec.wrapper.communication_step == 0.001

    def test_fmus_extracted_into_workspace(self, make_ssp, tmp_path):
        ssp_path = make_ssp(
            fmu_sources={"src": "./resources/src.fmu"},
        )
        spec = parse_spec(ssp_path, workspace_dir=str(tmp_path))
        extracted = spec.fmus["src"].path
        assert os.path.dirname(extracted) == str(tmp_path)
        assert os.path.basename(extracted) == "src.fmu"
        with zipfile.ZipFile(extracted) as zf:
            assert "modelDescription.xml" in zf.namelist()

    def test_missing_file(self, tmp_path):
        with pytest.raises(SpecValidationError) as exc:
            parse_spec(os.path.join(str(tmp_path), "nope.ssp"), workspace_dir=str(tmp_path))
        assert "not found" in str(exc.value)

    def test_non_ssp_extension(self, tmp_path):
        path = os.path.join(str(tmp_path), "spec.txt")
        with open(path, "w") as f:
            f.write("x")
        with pytest.raises(SpecValidationError) as exc:
            parse_spec(path, workspace_dir=str(tmp_path))
        assert ".ssp" in str(exc.value)

    def test_not_a_zip(self, tmp_path):
        path = os.path.join(str(tmp_path), "bad.ssp")
        with open(path, "w") as f:
            f.write("not a zip")
        with pytest.raises(SpecValidationError) as exc:
            parse_spec(path, workspace_dir=str(tmp_path))
        assert "archive" in str(exc.value) or "zip" in str(exc.value).lower()

    def test_missing_system_structure(self, tmp_path):
        import tempfile
        fd, path = tempfile.mkstemp(suffix=".ssp")
        os.close(fd)
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("resources/x.fmu", b"data")
        try:
            with pytest.raises(SpecValidationError) as exc:
                parse_spec(path, workspace_dir=str(tmp_path))
            assert "SystemStructure.ssd" in str(exc.value)
        finally:
            os.unlink(path)


class TestSspValidation:
    """Invalid .ssp packages raise SpecValidationError with clear messages."""

    def test_missing_component_source(self, tmp_path):
        # Build the archive manually: a component with an empty source URI.
        from tests.helpers import build_ssp_document
        doc = build_ssp_document(fmu_sources={"src": ""})
        from pyssp_standard.standard.ssp1.codec.ssd_codec import Ssp1SsdCodec
        path = os.path.join(str(tmp_path), "missing_source.ssp")
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("SystemStructure.ssd", Ssp1SsdCodec().serialize(doc))
        with pytest.raises(SpecValidationError) as exc:
            parse_spec(path, workspace_dir=str(tmp_path))
        assert "missing required attribute 'source'" in str(exc.value)

    def test_missing_fmu_member(self, tmp_path):
        # Component source points at a member that is not bundled in the archive.
        from tests.helpers import build_ssp_document
        doc = build_ssp_document(fmu_sources={"src": "resources/missing.fmu"})
        from pyssp_standard.standard.ssp1.codec.ssd_codec import Ssp1SsdCodec
        path = os.path.join(str(tmp_path), "missing_member.ssp")
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("SystemStructure.ssd", Ssp1SsdCodec().serialize(doc))
        with pytest.raises(SpecValidationError) as exc:
            parse_spec(path, workspace_dir=str(tmp_path))
        assert "member not found" in str(exc.value)

    def test_unknown_component_in_connection(self, make_ssp, tmp_path):
        ssp_path = make_ssp(
            fmu_sources=_valid_fmu_sources(),
            connectors=[],
            connections=[("nonexistent", "x", "tgt", "u")],
        )
        with pytest.raises(SpecValidationError) as exc:
            parse_spec(ssp_path, workspace_dir=str(tmp_path))
        assert "nonexistent" in str(exc.value)

    def test_boundary_connection_rejected(self, make_ssp, tmp_path):
        ssp_path = make_ssp(
            fmu_sources=_valid_fmu_sources(),
            connectors=[],
            connections=[("", "y", "tgt", "u")],
        )
        with pytest.raises(SpecValidationError) as exc:
            parse_spec(ssp_path, workspace_dir=str(tmp_path))
        assert "not supported" in str(exc.value)

    def test_duplicate_connector_name(self, make_ssp, tmp_path):
        ssp_path = make_ssp(
            fmu_sources=_valid_fmu_sources(),
            connectors=[
                {"element": "src/u", "name": "dup", "kind": "input"},
                {"element": "tgt/u", "name": "dup", "kind": "input"},
            ],
        )
        with pytest.raises(SpecValidationError) as exc:
            parse_spec(ssp_path, workspace_dir=str(tmp_path))
        assert "duplicate" in str(exc.value)

    def test_invalid_connector_kind(self, make_ssp, tmp_path):
        ssp_path = make_ssp(
            fmu_sources=_valid_fmu_sources(),
            connectors=[{"element": "src/u", "name": "x", "kind": "clamp"}],
        )
        with pytest.raises(SpecValidationError) as exc:
            parse_spec(ssp_path, workspace_dir=str(tmp_path))
        assert "kind" in str(exc.value)

    def test_invalid_connector_type(self, make_ssp, tmp_path):
        ssp_path = make_ssp(
            fmu_sources=_valid_fmu_sources(),
            connectors=[
                {"element": "src/u", "name": "x", "kind": "input", "type_name": "Complex"}
            ],
        )
        with pytest.raises(SpecValidationError) as exc:
            parse_spec(ssp_path, workspace_dir=str(tmp_path))
        assert "Complex" in str(exc.value)

    def test_connector_unknown_fmu(self, make_ssp, tmp_path):
        ssp_path = make_ssp(
            fmu_sources=_valid_fmu_sources(),
            connectors=[{"element": "ghost/u", "name": "x", "kind": "input"}],
        )
        with pytest.raises(SpecValidationError) as exc:
            parse_spec(ssp_path, workspace_dir=str(tmp_path))
        assert "ghost" in str(exc.value)

    def test_malformed_connector_element_path(self, make_ssp, tmp_path):
        ssp_path = make_ssp(
            fmu_sources=_valid_fmu_sources(),
            connectors=[{"element": "no_separator", "name": "x", "kind": "input"}],
        )
        with pytest.raises(SpecValidationError) as exc:
            parse_spec(ssp_path, workspace_dir=str(tmp_path))
        assert "element" in str(exc.value)

    def test_step_size_gt_comm_step(self, make_ssp, tmp_path):
        solver = ET.Element("Solver")
        solver.set("type", "fixed_step")
        solver.set("stepSize", "0.1")
        solver.set("communicationStep", "0.01")
        wrapper = ET.Element("Wrapper")
        wrapper.set("communicationStep", "0.01")
        ssp_path = make_ssp(
            fmu_sources=_valid_fmu_sources(),
            connectors=[],
            annotations=[("cs-fmu-packager", [solver, wrapper])],
        )
        with pytest.raises(SpecValidationError) as exc:
            parse_spec(ssp_path, workspace_dir=str(tmp_path))
        assert "step_size" in str(exc.value)

    def test_comm_step_mismatch(self, make_ssp, tmp_path):
        solver = ET.Element("Solver")
        solver.set("type", "fixed_step")
        solver.set("stepSize", "0.001")
        solver.set("communicationStep", "0.01")
        wrapper = ET.Element("Wrapper")
        wrapper.set("communicationStep", "0.02")
        ssp_path = make_ssp(
            fmu_sources=_valid_fmu_sources(),
            connectors=[],
            annotations=[("cs-fmu-packager", [solver, wrapper])],
        )
        with pytest.raises(SpecValidationError) as exc:
            parse_spec(ssp_path, workspace_dir=str(tmp_path))
        assert "communication_step" in str(exc.value)


class TestVendorConfig:
    """The cs-fmu-packager vendor annotation carries solver/wrapper policy."""

    def test_solver_and_algebraic_loop_config(self, make_ssp, tmp_path):
        solver = ET.Element("Solver")
        solver.set("type", "fixed_step")
        solver.set("stepSize", "0.0005")
        solver.set("communicationStep", "0.01")
        loop = ET.Element("AlgebraicLoop")
        loop.set("maxIterations", "50")
        loop.set("tolerance", "1e-8")
        wrapper = ET.Element("Wrapper")
        wrapper.set("communicationStep", "0.01")
        ssp_path = make_ssp(
            fmu_sources=_valid_fmu_sources(),
            connectors=_connectors_for_two_fmus(),
            annotations=[("cs-fmu-packager", [solver, loop, wrapper])],
        )
        spec = parse_spec(ssp_path, workspace_dir=str(tmp_path))
        assert spec.solver.type == "fixed_step"
        assert spec.solver.step_size == 0.0005
        assert spec.solver.communication_step == 0.01
        assert spec.solver.algebraic_loop.max_iterations == 50
        assert spec.solver.algebraic_loop.tolerance == 1e-8
        assert spec.wrapper.communication_step == 0.01

    def test_unknown_annotation_ignored(self, make_ssp, tmp_path):
        solver = ET.Element("Solver")
        solver.set("stepSize", "0.5")
        ssp_path = make_ssp(
            fmu_sources=_valid_fmu_sources(),
            connectors=_connectors_for_two_fmus(),
            annotations=[("some-other-tool", [solver])],
        )
        spec = parse_spec(ssp_path, workspace_dir=str(tmp_path))
        # Foreign annotation is ignored; defaults remain.
        assert spec.solver.step_size == 0.001

    def test_invalid_solver_type(self, make_ssp, tmp_path):
        solver = ET.Element("Solver")
        solver.set("type", "adaptive")
        ssp_path = make_ssp(
            fmu_sources=_valid_fmu_sources(),
            annotations=[("cs-fmu-packager", [solver])],
        )
        with pytest.raises(SpecValidationError) as exc:
            parse_spec(ssp_path, workspace_dir=str(tmp_path))
        assert "fixed_step" in str(exc.value)


class TestBoundaryVariables:
    """System-level connectors become boundary variables (edge wiring)."""

    def test_parameter_start_from_binding(self, make_ssp, tmp_path):
        ssp_path = make_ssp(
            fmu_sources=_valid_fmu_sources(),
            connectors=[
                {"element": "src/p", "name": "p1", "kind": "parameter", "type_name": "Real"},
            ],
            parameters=[("src/p", "Real", 5.0)],
        )
        spec = parse_spec(ssp_path, workspace_dir=str(tmp_path))
        assert len(spec.variables) == 1
        var = spec.variables[0]
        assert var.causality == "parameter"
        assert var.target_fmu == "src"
        assert var.target_variable == "p"
        assert var.start == 5.0

    def test_calculated_parameter_becomes_readable_output(self, make_ssp, tmp_path):
        ssp_path = make_ssp(
            fmu_sources=_valid_fmu_sources(),
            connectors=[
                {"element": "src/p", "name": "calc", "kind": "calculatedParameter"},
            ],
        )
        spec = parse_spec(ssp_path, workspace_dir=str(tmp_path))
        assert spec.variables[0].causality == "output"
        assert spec.variables[0].source_fmu == "src"
        assert spec.variables[0].source_variable == "p"

    def test_no_connectors_means_empty_variables(self, make_ssp, tmp_path):
        ssp_path = make_ssp(
            fmu_sources=_valid_fmu_sources(),
            connectors=[],
        )
        spec = parse_spec(ssp_path, workspace_dir=str(tmp_path))
        assert spec.variables == []  # mapper auto-discovery fills these (IMP-013)


class TestTolerantNamespaceRemapping:
    """Non-canonical SSD roots/namespaces are normalized before parsing."""

    _VARIANT_SSD = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<SystemStructure xmlns="http://example.com/ns" '
        'xmlns:ssc="http://ssp-standard.org/SSP1/SystemStructureCommon" '
        'name="test_sys" version="1.0">\n'
        '  <System name="System">\n'
        '    <Connectors>\n'
        '      <Connector name="input1" kind="input" element="src/u">\n'
        '        <ssc:Real/>\n'
        '      </Connector>\n'
        '      <Connector name="output1" kind="output" element="tgt/y">\n'
        '        <ssc:Real/>\n'
        '      </Connector>\n'
        '    </Connectors>\n'
        '    <Elements>\n'
        '      <Component name="src" source="resources/src.fmu"/>\n'
        '      <Component name="tgt" source="resources/tgt.fmu"/>\n'
        '    </Elements>\n'
        '    <Connections>\n'
        '      <Connection startElement="src" startConnector="y" '
        'endElement="tgt" endConnector="u"/>\n'
        '    </Connections>\n'
        '  </System>\n'
        '</SystemStructure>'
    )

    @staticmethod
    def _write_ssp(tmp_path, ssd_xml, name="variant.ssp"):
        from tests.helpers import make_fmu_bytes
        path = os.path.join(str(tmp_path), name)
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("SystemStructure.ssd", ssd_xml)
            zf.writestr("resources/src.fmu", make_fmu_bytes())
            zf.writestr("resources/tgt.fmu", make_fmu_bytes())
        return path

    def test_foreign_root_tag_and_namespace_normalized(self, tmp_path):
        ssp_path = self._write_ssp(tmp_path, self._VARIANT_SSD)
        spec = parse_spec(ssp_path, workspace_dir=str(tmp_path))
        assert spec.metadata["identifier"] == "test_sys"
        assert set(spec.fmus) == {"src", "tgt"}
        assert len(spec.connections) == 1
        assert spec.connections[0].source_fmu == "src"
        assert spec.connections[0].source_variable == "y"
        assert spec.connections[0].target_fmu == "tgt"
        assert spec.connections[0].target_variable == "u"
        assert [v.name for v in spec.variables] == ["input1", "output1"]
        assert spec.variables[0].causality == "input"
        assert spec.variables[1].causality == "output"

    def test_missing_root_name_and_version_defaulted(self, tmp_path):
        ssd = (
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<SystemStructure xmlns="http://example.com/ns">\n'
            '  <System name="System">\n'
            '    <Elements>\n'
            '      <Component name="src" source="resources/src.fmu"/>\n'
            '    </Elements>\n'
            '  </System>\n'
            '</SystemStructure>'
        )
        ssp_path = self._write_ssp(tmp_path, ssd)
        spec = parse_spec(ssp_path, workspace_dir=str(tmp_path))
        assert spec.metadata["identifier"] == "system"


class TestConfigErrorPaths:
    """Invalid numeric config annotation values raise SpecValidationError."""

    @pytest.mark.parametrize("value", ["0", "-1", "abc"])
    def test_invalid_step_size_rejected(self, make_ssp, tmp_path, value):
        solver = ET.Element("Solver")
        solver.set("type", "fixed_step")
        solver.set("stepSize", value)
        ssp_path = make_ssp(
            fmu_sources=_valid_fmu_sources(),
            connectors=[],
            annotations=[("cs-fmu-packager", [solver])],
        )
        with pytest.raises(SpecValidationError) as exc:
            parse_spec(ssp_path, workspace_dir=str(tmp_path))
        assert "stepSize" in str(exc.value)
        assert "must be a positive" in str(exc.value)

    @pytest.mark.parametrize("value", ["0", "-3", "x"])
    def test_invalid_max_iterations_rejected(self, make_ssp, tmp_path, value):
        loop = ET.Element("AlgebraicLoop")
        loop.set("maxIterations", value)
        ssp_path = make_ssp(
            fmu_sources=_valid_fmu_sources(),
            connectors=[],
            annotations=[("cs-fmu-packager", [loop])],
        )
        with pytest.raises(SpecValidationError) as exc:
            parse_spec(ssp_path, workspace_dir=str(tmp_path))
        assert "maxIterations" in str(exc.value)
        assert "must be a positive" in str(exc.value)


class TestConnectorKinds:
    """Connector kinds map onto wrapper variable causalities."""

    def test_inout_kind_maps_to_input(self, make_ssp, tmp_path):
        ssp_path = make_ssp(
            fmu_sources=_valid_fmu_sources(),
            connectors=[
                {"element": "src/u", "name": "io", "kind": "inout", "type_name": "Real"},
            ],
        )
        spec = parse_spec(ssp_path, workspace_dir=str(tmp_path))
        assert len(spec.variables) == 1
        var = spec.variables[0]
        assert var.causality == "input"
        assert var.target_fmu == "src"
        assert var.target_variable == "u"


class TestParameterValueCoercion:
    """Parameter start values are coerced to typed Python values."""

    def test_integer_parameter_start_is_int(self, make_ssp, tmp_path):
        ssp_path = make_ssp(
            fmu_sources=_valid_fmu_sources(),
            connectors=[
                {"element": "src/p", "name": "p1", "kind": "parameter", "type_name": "Integer"},
            ],
            parameters=[("src/p", "Integer", 42)],
        )
        spec = parse_spec(ssp_path, workspace_dir=str(tmp_path))
        start = spec.variables[0].start
        assert start == 42
        assert isinstance(start, int)

    def test_boolean_parameter_start_true(self, make_ssp, tmp_path):
        ssp_path = make_ssp(
            fmu_sources=_valid_fmu_sources(),
            connectors=[
                {"element": "src/p", "name": "p1", "kind": "parameter", "type_name": "Boolean"},
            ],
            parameters=[("src/p", "Boolean", True)],
        )
        spec = parse_spec(ssp_path, workspace_dir=str(tmp_path))
        assert spec.variables[0].start is True

    def test_boolean_parameter_from_string_true(self, make_ssp, tmp_path):
        ssp_path = make_ssp(
            fmu_sources=_valid_fmu_sources(),
            connectors=[
                {"element": "src/p", "name": "p1", "kind": "parameter", "type_name": "Boolean"},
            ],
            parameters=[("src/p", "Boolean", "TRUE")],
        )
        spec = parse_spec(ssp_path, workspace_dir=str(tmp_path))
        assert spec.variables[0].start is True

    def test_uncoercible_parameter_start_none(self, make_ssp, tmp_path):
        ssp_path = make_ssp(
            fmu_sources=_valid_fmu_sources(),
            connectors=[
                {"element": "src/p", "name": "p1", "kind": "parameter", "type_name": "Real"},
            ],
            parameters=[("src/p", "Real", "not-a-number")],
        )
        spec = parse_spec(ssp_path, workspace_dir=str(tmp_path))
        assert spec.variables[0].start is None


class TestNestedSystemRejected:
    """Nested <System> elements are not supported at the top level."""

    def test_nested_system_element_rejected(self, tmp_path):
        from tests.helpers import build_ssp_document
        from pyssp_standard.standard.ssp1.codec.ssd_codec import Ssp1SsdCodec
        from pyssp_standard.standard.ssp1.model.ssd_model import Ssd1System
        doc = build_ssp_document(fmu_sources={"src": "resources/src.fmu"})
        doc.system.elements.append(Ssd1System(name="nested"))
        path = os.path.join(str(tmp_path), "nested.ssp")
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("SystemStructure.ssd", Ssp1SsdCodec().serialize(doc))
            zf.writestr("resources/src.fmu", b"data")
        with pytest.raises(SpecValidationError) as exc:
            parse_spec(path, workspace_dir=str(tmp_path))
        assert "nested <System> elements are not supported" in str(exc.value)