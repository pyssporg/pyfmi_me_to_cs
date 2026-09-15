"""Tests for FMU inspection."""
from __future__ import annotations

import zipfile

import pytest

from tests.helpers import make_test_fmu
from cs_fmu_packager.errors import FmuInspectionError
from cs_fmu_packager.fmu_reader import inspect_fmu
from pyssp_standard.standard.fmi2.model.model_description import Fmi2ModelDescriptionDocument


MINIMAL_ME_MODEL_DESC = """<?xml version="1.0" encoding="UTF-8"?>
<fmiModelDescription
  fmiVersion="2.0"
  modelName="TestFMU"
  guid="{8c4e810f-3df3-4a00-8276-176fa3c9f000}"
  generationTool="test"
  variableNamingConvention="structured"
  numberOfEventIndicators="0"
>
  <ModelExchange
    modelIdentifier="TestFMU"
    canGetAndSetFMUstate="true"
    canSerializeFMUstate="true"
    providesDirectionalDerivatives="false"
  />
  <ModelVariables>
    <ScalarVariable
      name="u"
      valueReference="0"
      causality="input"
      variability="continuous"
    >
      <Real start="0.0" />
    </ScalarVariable>
    <ScalarVariable
      name="y"
      valueReference="1"
      causality="output"
      variability="continuous"
    >
      <Real />
    </ScalarVariable>
    <ScalarVariable
      name="x"
      valueReference="2"
      causality="local"
      variability="continuous"
    >
      <Real start="0.0" />
    </ScalarVariable>
  </ModelVariables>
  <ModelStructure>
    <Outputs>
      <Unknown index="1" dependencies="0" />
    </Outputs>
    <ContinuousStateDerivatives>
      <Unknown index="2" dependencies="0" />
    </ContinuousStateDerivatives>
  </ModelStructure>
</fmiModelDescription>"""


class TestFmuInspection:
    def test_inspect_valid_fmu(self, tmp_fmu_path):
        """Test basic FMU inspection."""
        make_test_fmu(tmp_fmu_path, MINIMAL_ME_MODEL_DESC)

        doc = inspect_fmu(tmp_fmu_path)
        assert doc.fmi_version == "2.0"
        assert doc.model_name == "TestFMU"
        assert doc.capabilities is not None
        assert doc.capabilities.model_identifier == "TestFMU"
        assert len(doc.variables) == 3

        # Build lookup for variable assertions
        var_map = {v.name: v for v in doc.variables}
        assert "u" in var_map
        assert var_map["u"].causality == "input"
        assert var_map["u"].value_reference == 0

        assert "y" in var_map
        assert var_map["y"].causality == "output"

        assert "x" in var_map
        assert var_map["x"].causality == "local"

    def test_inspect_fmu_model_identifier(self, tmp_fmu_path):
        """Fmi2ModelDescriptionDocument.capabilities should contain modelIdentifier."""
        make_test_fmu(tmp_fmu_path, MINIMAL_ME_MODEL_DESC)
        doc = inspect_fmu(tmp_fmu_path)
        assert doc.capabilities is not None
        assert doc.capabilities.model_identifier == "TestFMU"

    def test_inspect_nonexistent_fmu(self):
        with pytest.raises(FmuInspectionError) as exc:
            inspect_fmu("/nonexistent/path.fmu")
        assert "not found" in str(exc.value)

    def test_inspect_not_a_zip(self, tmp_fmu_path):
        with open(tmp_fmu_path, "w") as f:
            f.write("not a zip file")
        with pytest.raises(FmuInspectionError) as exc:
            inspect_fmu(tmp_fmu_path)
        assert "valid ZIP" in str(exc.value)

    def test_inspect_missing_model_desc(self, tmp_fmu_path):
        with zipfile.ZipFile(tmp_fmu_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("not_modelDescription.xml", "garbage")

        with pytest.raises(FmuInspectionError) as exc:
            inspect_fmu(tmp_fmu_path)
        assert "missing modelDescription.xml" in str(exc.value)

    def test_inspect_wrong_fmi_version(self, tmp_fmu_path):
        model_desc_wrong = """<?xml version="1.0" encoding="UTF-8"?>
<fmiModelDescription fmiVersion="1.0" modelName="OldFMU" guid="abc">
  <ModelExchange modelIdentifier="OldFMU" />
</fmiModelDescription>"""
        make_test_fmu(tmp_fmu_path, model_desc_wrong)
        with pytest.raises(FmuInspectionError) as exc:
            inspect_fmu(tmp_fmu_path)
        # The fork cannot parse non-FMI-2.0 documents at all
        assert "Failed to read FMU" in str(exc.value)

    def test_inspect_not_me_fmu(self, tmp_fmu_path):
        """CS-only FMU should be rejected."""
        model_desc_cs = """<?xml version="1.0" encoding="UTF-8"?>
<fmiModelDescription fmiVersion="2.0" modelName="CSFMU" guid="abc">
  <CoSimulation modelIdentifier="CSFMU" />
</fmiModelDescription>"""
        make_test_fmu(tmp_fmu_path, model_desc_cs)
        with pytest.raises(FmuInspectionError) as exc:
            inspect_fmu(tmp_fmu_path)
        assert "not a ModelExchange" in str(exc.value)

    def test_inspect_fmu_returns_variable_details(self, tmp_fmu_path):
        """inspect_fmu should return variables with correct metadata."""
        make_test_fmu(tmp_fmu_path, MINIMAL_ME_MODEL_DESC)
        doc = inspect_fmu(tmp_fmu_path)
        assert len(doc.variables) > 0
        # Check that at least one variable has a value_reference
        for var in doc.variables:
            assert var.value_reference >= 0
            assert var.type_name in ("Real", "Integer", "Boolean", "String", "Enumeration")
            assert var.causality in ("input", "output", "parameter", "local", "independent")

    def test_inspect_non_fmu_extension(self, tmp_path):
        """A path not ending in .fmu is rejected before the archive is opened."""
        model_txt = tmp_path / "model.txt"
        model_txt.write_text("not an fmu")
        with pytest.raises(FmuInspectionError) as exc:
            inspect_fmu(str(model_txt))
        assert "expected .fmu extension" in str(exc.value)

    def test_inspect_malformed_model_desc(self, tmp_fmu_path):
        """Malformed modelDescription.xml hits the ParseError branch."""
        malformed_xml = """<?xml version="1.0" encoding="UTF-8"?>
<fmiModelDescription>
  <ModelExchange>"""
        make_test_fmu(tmp_fmu_path, malformed_xml)
        with pytest.raises(FmuInspectionError) as exc:
            inspect_fmu(tmp_fmu_path)
        assert "invalid modelDescription.xml" in str(exc.value)

    def test_inspect_fmi_1_0_docs_version_branch_unreachable(self, tmp_fmu_path):
        """Document the FMI-version branch in fmu_reader.py:59-62.

        A fmiVersion="2.0" + CoSimulation doc is rejected with "not a
        ModelExchange" (see test_inspect_not_me_fmu), so the "unsupported
        FMI version" branch is only reachable for a parsed 2.0 doc that is
        not ME -- which never happens since interface_type would be CS.
        A fmiVersion="1.0" doc never reaches the dedicated version branch
        either: the parser rejects non-2.0 documents first, so the generic
        "Failed to read FMU" path fires instead.
        """
        model_desc_10 = """<?xml version="1.0" encoding="UTF-8"?>
<fmiModelDescription fmiVersion="1.0" modelName="OldFMU" guid="abc">
  <ModelExchange modelIdentifier="OldFMU" />
</fmiModelDescription>"""
        make_test_fmu(tmp_fmu_path, model_desc_10)
        with pytest.raises(FmuInspectionError) as exc:
            inspect_fmu(tmp_fmu_path)
        assert "Failed to read FMU" in str(exc.value)

    def test_inspect_integer_parameter_typed_metadata(self, tmp_fmu_path):
        """Non-Real variables expose type_name and value_reference."""
        model_desc_int_param = """<?xml version="1.0" encoding="UTF-8"?>
<fmiModelDescription
  fmiVersion="2.0"
  modelName="TestFMU"
  guid="{8c4e810f-3df3-4a00-8276-176fa3c9f000}"
  generationTool="test"
  variableNamingConvention="structured"
  numberOfEventIndicators="0"
>
  <ModelExchange
    modelIdentifier="TestFMU"
    canGetAndSetFMUstate="true"
    canSerializeFMUstate="true"
    providesDirectionalDerivatives="false"
  />
  <ModelVariables>
    <ScalarVariable
      name="p"
      valueReference="5"
      causality="parameter"
      variability="fixed"
    >
      <Integer start="3" />
    </ScalarVariable>
  </ModelVariables>
  <ModelStructure />
</fmiModelDescription>"""
        make_test_fmu(tmp_fmu_path, model_desc_int_param)
        doc = inspect_fmu(tmp_fmu_path)
        (p,) = (v for v in doc.variables if v.name == "p")
        assert p.type_name == "Integer"
        assert p.value_reference == 5
        assert p.causality == "parameter"
        assert p.variability == "fixed"