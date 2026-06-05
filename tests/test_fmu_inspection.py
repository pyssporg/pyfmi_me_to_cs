"""Tests for FMU inspection."""
from __future__ import annotations

import os
import tempfile
import zipfile

import pytest

from cs_fmu_packager.errors import FmuInspectionError
from cs_fmu_packager.fmu_reader import inspect_fmu
from cs_fmu_packager.models import FmuMetadata


def _create_minimal_me_fmu(path: str) -> None:
    """Create a minimal FMI 2.0 Model Exchange FMU for testing."""
    model_desc = """<?xml version="1.0" encoding="UTF-8"?>
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

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("modelDescription.xml", model_desc)


class TestFmuInspection:
    def test_inspect_valid_fmu(self):
        """Test basic FMU inspection."""
        fd, path = tempfile.mkstemp(suffix=".fmu")
        os.close(fd)
        _create_minimal_me_fmu(path)

        meta = inspect_fmu(path)
        assert meta.fmi_version == "2.0"
        assert meta.model_name == "TestFMU"
        assert "ModelExchange" in meta.model_types
        assert len(meta.variables) == 3

        # Check specific variables
        assert "u" in meta.variables
        assert meta.variables["u"].causality == "input"
        assert meta.variables["u"].value_reference == 0

        assert "y" in meta.variables
        assert meta.variables["y"].causality == "output"

        assert "x" in meta.variables
        assert meta.variables["x"].causality == "local"

        os.unlink(path)

    def test_inspect_nonexistent_fmu(self):
        with pytest.raises(FmuInspectionError) as exc:
            inspect_fmu("/nonexistent/path.fmu")
        assert "not found" in str(exc.value)

    def test_inspect_not_a_zip(self):
        fd, path = tempfile.mkstemp(suffix=".fmu")
        with os.fdopen(fd, "w") as f:
            f.write("not a zip file")
        with pytest.raises(FmuInspectionError) as exc:
            inspect_fmu(path)
        assert "valid ZIP" in str(exc.value)
        os.unlink(path)

    def test_inspect_missing_model_desc(self):
        fd, path = tempfile.mkstemp(suffix=".fmu")
        os.close(fd)
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("not_modelDescription.xml", "garbage")

        with pytest.raises(FmuInspectionError) as exc:
            inspect_fmu(path)
        assert "missing modelDescription.xml" in str(exc.value)
        os.unlink(path)

    def test_inspect_wrong_fmi_version(self):
        model_desc_wrong = """<?xml version="1.0" encoding="UTF-8"?>
<fmiModelDescription fmiVersion="1.0" modelName="OldFMU" guid="abc">
  <ModelExchange modelIdentifier="OldFMU" />
</fmiModelDescription>"""
        fd, path = tempfile.mkstemp(suffix=".fmu")
        os.close(fd)
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("modelDescription.xml", model_desc_wrong)
        with pytest.raises(FmuInspectionError) as exc:
            inspect_fmu(path)
        assert "unsupported FMI version" in str(exc.value)
        os.unlink(path)

    def test_inspect_not_me_fmu(self):
        """CS-only FMU should be rejected."""
        model_desc_cs = """<?xml version="1.0" encoding="UTF-8"?>
<fmiModelDescription fmiVersion="2.0" modelName="CSFMU" guid="abc">
  <CoSimulation modelIdentifier="CSFMU" />
</fmiModelDescription>"""
        fd, path = tempfile.mkstemp(suffix=".fmu")
        os.close(fd)
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("modelDescription.xml", model_desc_cs)
        with pytest.raises(FmuInspectionError) as exc:
            inspect_fmu(path)
        assert "not a ModelExchange" in str(exc.value)
        os.unlink(path)