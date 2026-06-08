"""Tests for FMU inspection."""
from __future__ import annotations

import zipfile

import pytest

from tests.helpers import make_test_fmu
from cs_fmu_packager.errors import FmuInspectionError
from cs_fmu_packager.fmu_reader import inspect_fmu
from cs_fmu_packager.models import FmuMetadata


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

        meta = inspect_fmu(tmp_fmu_path)
        assert meta.fmi_version == "2.0"
        assert meta.model_name == "TestFMU"
        assert meta.model_identifier == "TestFMU"
        assert len(meta.variables) == 3

        # Check specific variables
        assert "u" in meta.variables
        assert meta.variables["u"].causality == "input"
        assert meta.variables["u"].value_reference == 0

        assert "y" in meta.variables
        assert meta.variables["y"].causality == "output"

        assert "x" in meta.variables
        assert meta.variables["x"].causality == "local"

    def test_inspect_fmu_model_identifier(self, tmp_fmu_path):
        """FmuMetadata should contain modelIdentifier parsed from XML."""
        make_test_fmu(tmp_fmu_path, MINIMAL_ME_MODEL_DESC)
        meta = inspect_fmu(tmp_fmu_path)
        assert meta.model_identifier == "TestFMU"

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
        assert "unsupported FMI version" in str(exc.value)

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
        meta = inspect_fmu(tmp_fmu_path)
        assert len(meta.variables) > 0
        # Check that at least one variable has a value_reference
        for name, var in meta.variables.items():
            assert var.value_reference >= 0
            assert var.type in ("Real", "Integer", "Boolean", "String", "Enumeration")
            assert var.causality in ("input", "output", "parameter", "local", "independent")