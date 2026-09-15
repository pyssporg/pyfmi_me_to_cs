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


def _variability_for_causality(causality: str) -> str:
    return {
        "parameter": "parameter",
        "input": "continuous",
        "output": "continuous",
    }.get(causality, "continuous")


def _initial_for_causality(causality: str) -> str:
    """Legal (causality, variability, initial) triple per FMI 2.0 (p.53)."""
    if causality in ("input", "parameter"):
        return "exact"
    return "calculated"


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
        vr = var.wrapper_value_reference or var_index
        causality = var.causality
        variability = _variability_for_causality(causality)
        initial = _initial_for_causality(causality)

        var_type = var.variable_type or "Real"
        start_val = var.start
        if start_val is None and causality in ("input", "parameter"):
            # FMI 2.0 p.53: inputs/parameters carry a start value.
            start_val = 0 if var_type != "String" else ""

        unit_str = f' unit="{escape(var.unit)}"' if var.unit else ""
        desc_str = f' description="{escape(var.description)}"' if var.description else ""

        if var_type == "Integer":
            start_str = f' start="{int(start_val)}"' if start_val is not None else ""
            type_elem = f"<Integer{start_str} />"
        elif var_type == "Boolean":
            start_str = ""
            if start_val is not None:
                start_str = f' start="{"true" if start_val else "false"}"'
            type_elem = f"<Boolean{start_str} />"
        elif var_type == "String":
            start_str = f' start="{escape(str(start_val))}"' if start_val is not None else ""
            type_elem = f"<String{start_str} />"
        else:
            start_str = f' start="{start_val}"' if start_val is not None else ""
            type_elem = f"<Real{start_str}{unit_str} />"

        elem = f"""
      <ScalarVariable
        name="{escape(var.wrapper_name)}"
        valueReference="{vr}"
        causality="{causality}"
        variability="{variability}"
        initial="{initial}"{desc_str}
      >
        {type_elem}
      </ScalarVariable>"""
        var_elements.append(elem)
        var_index += 1

    variables_section = "\n".join(var_elements)

    # Internal FMU annotations
    internal_fmus = ", ".join(sorted(spec.fmus.keys()))
    num_loops = len(mapping.algebraic_loops)

    # Outputs section — Unknown index refers to the 1-based ScalarVariable
    # index, which equals the wrapper boundary value reference.
    output_elems = []
    for var in mapping.wrapper_outputs:
        idx = var.wrapper_value_reference or 0
        output_elems.append(
            f'      <Unknown index="{idx}" dependencies="" />'
        )
    outputs_section = "\n".join(output_elems)

    # Connection annotations (VendorAnnotations -> Tool)
    conn_elems = []
    for conn in mapping.connections:
        conn_elems.append(
            f'            <Connection source="{conn.source_fmu}.{conn.source_variable}" '
            f'target="{conn.target_fmu}.{conn.target_variable}" />'
        )
    conn_section = "\n".join(conn_elems)

    vendor_annotations = f"""  <VendorAnnotations>
    <Tool name="cs-fmu-packager">
      <CsFmuPackager
        solverType="fixed_step"
        solverStepSize="{spec.solver.step_size}"
        communicationStepSize="{spec.wrapper.communication_step}"
        internalFMUs="{escape(internal_fmus)}"
        algebraicLoopCount="{num_loops}"
        algebraicLoopMaxIterations="{spec.solver.algebraic_loop.max_iterations}"
        algebraicLoopTolerance="{spec.solver.algebraic_loop.tolerance}"
      >
        <InternalConnections>
          {conn_section}
        </InternalConnections>
      </CsFmuPackager>
    </Tool>
  </VendorAnnotations>
"""

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
    providesDirectionalDerivative="false"
    canRunAsynchronuously="false"
    canBeInstantiatedOnlyOncePerProcess="false"
    canNotUseMemoryManagementFunctions="false"
  >
  </CoSimulation>

  {vendor_annotations}

  <ModelVariables>
    {variables_section}
  </ModelVariables>

  <ModelStructure>
    <Outputs>
      {outputs_section}
    </Outputs>
  </ModelStructure>
</fmiModelDescription>
"""