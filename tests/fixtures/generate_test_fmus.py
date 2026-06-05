#!/usr/bin/env python3
"""Generate minimal FMI 2.0 Model Exchange FMUs for testing.

Creates simple test FMUs with known behavior:
- integrator: y' = u, y = x (integrator)
- gain: y = K*u (feed-through gain)
"""

from __future__ import annotations

import os
import zipfile
import xml.etree.ElementTree as ET
from typing import Optional


def _make_model_description(
    model_name: str,
    guid: str,
    model_identifier: str,
    variables_xml: str,
    outputs_xml: str,
    derivatives_xml: Optional[str] = None,
) -> str:
    """Build a modelDescription.xml string."""
    deriv_section = ""
    if derivatives_xml:
        deriv_section = f"""
    <ContinuousStateDerivatives>
{derivatives_xml}
    </ContinuousStateDerivatives>"""

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<fmiModelDescription
  fmiVersion="2.0"
  modelName="{model_name}"
  guid="{guid}"
  generationTool="cs-fmu-packager-test-generator"
  generationDateAndTime="2020-01-01T00:00:00Z"
  variableNamingConvention="structured"
  numberOfEventIndicators="0"
>
  <ModelExchange
    modelIdentifier="{model_identifier}"
    canGetAndSetFMUstate="false"
    canSerializeFMUstate="false"
    providesDirectionalDerivatives="false"
    completedIntegratorStepNotNeeded="true"
  />
  <ModelVariables>
    {variables_xml}
  </ModelVariables>
  <ModelStructure>
    <Outputs>
{outputs_xml}
    </Outputs>
{deriv_section}
  </ModelStructure>
</fmiModelDescription>"""


def create_integrator_fmu(path: str, gain: float = 1.0) -> str:
    """Create a simple integrator FMU: dx/dt = gain * u, y = x.

    Variables:
        u (input, Real, vr=0)
        x (local/continuous, Real, vr=1, start=0)
        y (output, Real, vr=2)

    Returns:
        The GUID of the generated FMU.
    """
    guid = "{8c4e810f-3df3-4a00-8276-176fa3c9f001}"
    vars_xml = f"""
      <ScalarVariable name="u" valueReference="0" causality="input" variability="continuous">
        <Real start="0.0" />
      </ScalarVariable>
      <ScalarVariable name="x" valueReference="1" causality="local" variability="continuous">
        <Real start="0.0" />
      </ScalarVariable>
      <ScalarVariable name="y" valueReference="2" causality="output" variability="continuous">
        <Real />
      </ScalarVariable>"""
    outputs_xml = """      <Unknown index="2" dependencies="1" dependenciesKind="dependent" />"""
    derivs_xml = """      <Unknown index="1" dependencies="0" dependenciesKind="dependent" />"""

    model_desc = _make_model_description(
        "Integrator", guid, "Integrator", vars_xml, outputs_xml, derivs_xml
    )

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("modelDescription.xml", model_desc)

    return guid


def create_gain_fmu(path: str, k: float = 2.0) -> str:
    """Create a simple gain FMU: y = k * u.

    Variables:
        u (input, Real, vr=0)
        y (output, Real, vr=1)

    Returns:
        The GUID of the generated FMU.
    """
    guid = "{8c4e810f-3df3-4a00-8276-176fa3c9f002}"
    vars_xml = f"""
      <ScalarVariable name="u" valueReference="0" causality="input" variability="continuous">
        <Real start="0.0" />
      </ScalarVariable>
      <ScalarVariable name="y" valueReference="1" causality="output" variability="continuous">
        <Real />
      </ScalarVariable>"""
    outputs_xml = """      <Unknown index="1" dependencies="0" dependenciesKind="dependent" />"""

    model_desc = _make_model_description(
        "Gain", guid, "Gain", vars_xml, outputs_xml
    )

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("modelDescription.xml", model_desc)

    return guid


def generate_test_fmus(output_dir: str) -> dict:
    """Generate all test FMU files and return their metadata.

    Args:
        output_dir: Directory to write FMU files into.

    Returns:
        Dict mapping FMU names to their metadata dicts.
    """
    os.makedirs(output_dir, exist_ok=True)

    result = {}

    # Integrator FMU
    integ_path = os.path.join(output_dir, "integrator.fmu")
    integ_guid = create_integrator_fmu(integ_path)
    result["integrator"] = {"path": integ_path, "guid": integ_guid}

    # Gain FMU
    gain_path = os.path.join(output_dir, "gain.fmu")
    gain_guid = create_gain_fmu(gain_path)
    result["gain"] = {"path": gain_path, "guid": gain_guid}

    return result


if __name__ == "__main__":
    import sys
    output_dir = sys.argv[1] if len(sys.argv) > 1 else "tests/fixtures"
    result = generate_test_fmus(output_dir)
    print(f"Generated {len(result)} test FMU(s) in {output_dir}:")
    for name, meta in result.items():
        print(f"  {name}: {meta['path']} (GUID: {meta['guid']})")