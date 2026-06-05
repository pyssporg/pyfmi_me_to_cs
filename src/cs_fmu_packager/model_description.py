"""FMU modelDescription.xml generation.

Generates a valid FMI 2.0 Co-Simulation modelDescription.xml
with proper capability flags and wrapper variable declarations.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import List
from xml.sax.saxutils import escape

from cs_fmu_packager.models import MappingTable, PackageSpec


def _derive_guid(spec: PackageSpec) -> str:
    """Derive a deterministic GUID from spec content."""
    content = (
        str(sorted(spec.fmus.keys()))
        + str(spec.solver.step_size)
        + str(spec.wrapper.communication_step)
        + str(len(spec.connections))
        + str(len(spec.variables))
    )
    h = hashlib.md5(content.encode())
    raw = h.digest()

    def _to_hex(b: bytes) -> str:
        return "".join(f"{c:02x}" for c in b)

    return (
        f"{_to_hex(raw[:4])}-{_to_hex(raw[4:6])}-"
        f"{_to_hex(raw[6:8])}-{_to_hex(raw[8:10])}-"
        f"{_to_hex(raw[10:16])}"
    )


def _now_iso() -> str:
    """Generate ISO timestamp for generation date."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _vr_for_index(index: int) -> int:
    """Generate a deterministic value reference for a wrapper variable index."""
    h = hashlib.md5(f"vr_{index}".encode())
    return int(h.hexdigest()[:8], 16) % 100000


def _variability_for_causality(causality: str) -> str:
    return {
        "parameter": "parameter",
        "input": "continuous",
        "output": "continuous",
    }.get(causality, "continuous")


def generate_model_description(spec: PackageSpec, mapping: MappingTable) -> str:
    """Generate modelDescription.xml for the packaged Co-Simulation FMU.

    Args:
        spec: The package specification.
        mapping: The resolved mapping table.

    Returns:
        XML string content.
    """
    fmu_name = spec.metadata.get("identifier", "cs_fmu")
    fmu_guid = _derive_guid(spec)
    description = spec.metadata.get(
        "description", f"Packaged Co-Simulation FMU: {fmu_name}"
    )
    author = spec.metadata.get("author", "cs-fmu-packager")
    version = spec.metadata.get("version", "0.1.0")

    # Build variable elements
    var_elements: List[str] = []
    var_index = 1
    for var in mapping.all_variables():
        vr = var_index
        start_str = f' start="{var.start}"' if var.start is not None else ""
        unit_str = f' unit="{escape(var.unit)}"' if var.unit else ""
        desc_str = f' description="{escape(var.description)}"' if var.description else ""

        # Determine XML type element based on variable type
        var_type = var.variable_type or "Real"
        if var_type == "Integer":
            type_elem = f"<Integer{start_str} />"
        elif var_type == "Boolean":
            start_b = ""
            if var.start is not None:
                start_b = f' start="{"true" if var.start else "false"}"'
            type_elem = f"<Boolean{start_b} />"
        elif var_type == "String":
            type_elem = f"<String{start_str} />"
        else:
            type_elem = f"<Real{start_str}{unit_str} />"

        elem = f"""
      <ScalarVariable
        name="{escape(var.wrapper_name)}"
        valueReference="{vr}"
        causality="{var.causality}"
        variability="{_variability_for_causality(var.causality)}"{desc_str}
      >
        {type_elem}
      </ScalarVariable>"""
        var_elements.append(elem)
        var_index += 1

    variables_section = "\n".join(var_elements)

    # Internal FMU annotations
    internal_fmus = ", ".join(sorted(spec.fmus.keys()))
    num_loops = len(mapping.algebraic_loops)

    # Outputs section
    output_elems = []
    for idx, var in enumerate(mapping.wrapper_outputs, 1):
        output_elems.append(
            f'      <Unknown index="{idx}" dependencies="" />'
        )
    outputs_section = "\n".join(output_elems)

    # Connection annotations
    conn_elems = []
    for conn in mapping.connections:
        conn_elems.append(
            f'            <Connection source="{conn.source_fmu}.{conn.source_variable}" '
            f'target="{conn.target_fmu}.{conn.target_variable}" />'
        )
    conn_section = "\n".join(conn_elems)

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<fmiModelDescription
  fmiVersion="2.0"
  modelName="{escape(fmu_name)}"
  guid="{escape(fmu_guid)}"
  description="{escape(description)}"
  author="{escape(author)}"
  version="{escape(version)}"
  generationTool="cs-fmu-packager {version}"
  generationDateAndTime="{_now_iso()}"
  variableNamingConvention="structured"
  numberOfEventIndicators="0"
>
  <CoSimulation
    modelIdentifier="{escape(fmu_name)}"
    canHandleVariableCommunicationStepSize="false"
    canInterpolateInputs="false"
    canGetAndSetFMUstate="false"
    canSerializeFMUstate="false"
    providesDirectionalDerivatives="false"
    canRunAsynchronuously="false"
    canBeInstantiatedOnlyOncePerProcess="false"
    canNotUseMemoryManagementFunctions="false"
  >
    <Annotations>
      <Annotation name="cs-fmu-packager">
        <Tool>
          <CsFmuPackager
            solverType="fixed_step"
            solverStepSize="{spec.solver.step_size}"
            communicationStepSize="{spec.wrapper.communication_step}"
            internalFMUs="{escape(internal_fmus)}"
            algebraicLoopCount="{num_loops}"
            algebraicLoopMaxIterations="{spec.solver.algebraic_loop.max_iterations}"
            algebraicLoopTolerance="{spec.solver.algebraic_loop.tolerance}"
          />
          <InternalConnections>
            {conn_section}
          </InternalConnections>
        </Tool>
      </Annotation>
    </Annotations>
  </CoSimulation>

  <ModelVariables>
    {variables_section}
  </ModelVariables>

  <ModelStructure>
    <Outputs>
      {outputs_section}
    </Outputs>
    <InitialUnknowns>
    </InitialUnknowns>
  </ModelStructure>
</fmiModelDescription>
"""