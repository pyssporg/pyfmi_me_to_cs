"""FMU modelDescription.xml generation.

The FMI 2.0 document is built with ``pyfmi_interfaces``: the FMI fields come
from its shared document model, and this module supplies only the
``cs-fmu-packager`` annotation payload (solver policy, internal FMU list, and
the internal connection graph) plus the local GUID and clock values. The
wrapper and solver C sources remain local; this module owns no FMI XML
spelling.
"""

from __future__ import annotations

from datetime import datetime, UTC
from xml.sax.saxutils import escape

from pyssp_standard.standard.fmi2.model import (
    Fmi2ElementInfo,
    Fmi2InterfaceAttributes,
    Fmi2ModelDescriptionDocument,
    Fmi2ModelStructure,
    Fmi2ScalarVariable,
    Fmi2Unknown,
)
from pyfmi_interfaces import (
    Annotation,
    ModelDescription,
    ModelDescriptionXmlCodec,
)
from pyfmi_interfaces.model_description.document import GENERATION_TOOL

from cs_fmu_packager.guid import derive_guid
from cs_fmu_packager.models import MappingTable, PackageSpec

#: The tool id carried by the one VendorAnnotations entry this package emits.
TOOL_NAME = "cs-fmu-packager"

#: Backwards-compatible name; the implementation lives in ``guid.py`` so the
#: FMI facade does not import the document writer.
_derive_guid = derive_guid

#: Capability flags spelled explicitly, in this order, for a v1 wrapper.
CAPABILITY_FLAGS = {
    "canHandleVariableCommunicationStepSize": "false",
    "canInterpolateInputs": "false",
    "canGetAndSetFMUstate": "false",
    "canSerializeFMUstate": "false",
    "providesDirectionalDerivative": "false",
    "canRunAsynchronuously": "false",
    "canBeInstantiatedOnlyOncePerProcess": "false",
    "canNotUseMemoryManagementFunctions": "false",
}


def _now_iso() -> str:
    """Generate ISO timestamp for generation date."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _variability_for_causality(causality: str) -> str:
    return {
        "parameter": "fixed",
        "input": "continuous",
        "output": "continuous",
    }.get(causality, "continuous")


def _initial_for_causality(causality: str) -> str:
    """Legal (causality, variability, initial) triple per FMI 2.0 (p.53)."""
    if causality in ("input", "parameter"):
        return "exact"
    return "calculated"


def _start_value(causality: str, variable_type: str, start):
    """FMI 2.0 p.53: inputs/parameters carry a start value.

    A Boolean start is spelled ``true``/``false``; the shared codec renders the
    typed value verbatim, so the FMI text is decided here.
    """
    if start is None and causality in ("input", "parameter"):
        start = 0 if variable_type != "String" else ""
    if variable_type == "Boolean" and start is not None:
        if isinstance(start, str):
            enabled = start.strip().lower() == "true"
        else:
            enabled = bool(start)
        return "true" if enabled else "false"
    return start


def _annotation_payload(spec: PackageSpec, mapping: MappingTable) -> str:
    """The ``<CsFmuPackager>`` fragment, emitted verbatim by the codec."""
    internal_fmus = ", ".join(sorted(spec.fmus.keys()))
    num_loops = len(mapping.algebraic_loops)
    connection_elements = "\n".join(
        f'            <Connection source="{conn.source_fmu}.{conn.source_variable}" '
        f'target="{conn.target_fmu}.{conn.target_variable}" />'
        for conn in mapping.connections
    )
    return f"""      <CsFmuPackager
        solverType="{spec.solver.type}"
        solverStepSize="{spec.solver.step_size}"
        solverTolerance="{spec.solver.tolerance}"
        communicationStepSize="{spec.wrapper.communication_step}"
        internalFMUs="{escape(internal_fmus)}"
        algebraicLoopCount="{num_loops}"
        algebraicLoopMaxIterations="{spec.solver.algebraic_loop.max_iterations}"
        algebraicLoopTolerance="{spec.solver.algebraic_loop.tolerance}"
      >
        <InternalConnections>
          {connection_elements}
        </InternalConnections>
      </CsFmuPackager>"""


def _document(spec: PackageSpec, mapping: MappingTable) -> Fmi2ModelDescriptionDocument:
    fmu_name = spec.metadata.get("identifier", "cs_fmu")
    description = spec.metadata.get(
        "description", f"Packaged Co-Simulation FMU: {fmu_name}"
    )
    author = spec.metadata.get("author", "cs-fmu-packager")
    version = spec.metadata.get("version", "0.1.0")

    variables = []
    var_index = 1
    for var in mapping.all_variables():
        value_reference = var.wrapper_value_reference or var_index
        variable_type = var.variable_type or "Real"
        variables.append(
            Fmi2ScalarVariable(
                name=var.wrapper_name,
                value_reference=value_reference,
                type_name=variable_type,
                description=var.description,
                causality=var.causality,
                variability=_variability_for_causality(var.causality),
                initial=_initial_for_causality(var.causality),
                start=_start_value(var.causality, variable_type, var.start),
                unit=var.unit,
            )
        )
        var_index += 1

    outputs = [
        Fmi2Unknown(index=var.wrapper_value_reference or 0)
        for var in mapping.wrapper_outputs
    ]

    return Fmi2ModelDescriptionDocument(
        root=Fmi2ElementInfo(tag="fmiModelDescription"),
        fmi_version="2.0",
        model_name=fmu_name,
        guid=derive_guid(spec),
        description=description,
        author=author,
        version=version,
        generation_tool=GENERATION_TOOL,
        generation_date_and_time=_now_iso(),
        variable_naming_convention="structured",
        number_of_event_indicators=0,
        interface_type="CoSimulation",
        capabilities=Fmi2InterfaceAttributes(
            model_identifier=fmu_name,
            extra_attributes=dict(CAPABILITY_FLAGS),
        ),
        variables=variables,
        model_structure=Fmi2ModelStructure(outputs=outputs),
    )


def generate_model_description(spec: PackageSpec, mapping: MappingTable) -> str:
    """Generate modelDescription.xml for the packaged Co-Simulation FMU.

    Args:
        spec: The package specification.
        mapping: The resolved mapping table.

    Returns:
        XML string content.
    """
    model = ModelDescription(
        _document(spec, mapping),
        [Annotation(TOOL_NAME, _annotation_payload(spec, mapping))],
    )
    return ModelDescriptionXmlCodec().serialize(model)
