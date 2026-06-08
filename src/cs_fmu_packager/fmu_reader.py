"""FMU inspection and modelDescription.xml parser.

Opens an FMI 2.0 Model Exchange FMU archive, validates its structure,
and extracts all metadata from modelDescription.xml.

Uses the pyssp_standard fork (jkCXf9X4/pyssp_standard, architecture_review branch)
for full typed dataclass access to FMI 2.0 model description elements,
eliminating the previous lxml dual-parsing workaround.
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional

from pyssp_standard.fmu import FMU

from cs_fmu_packager.errors import FmuInspectionError
from cs_fmu_packager.models import FmuMetadata, ScalarVariable


def inspect_fmu(path: str) -> FmuMetadata:
    """Open an FMU archive and extract metadata.

    Args:
        path: Path to the .fmu file.

    Returns:
        FmuMetadata with parsed modelDescription.xml contents.

    Raises:
        FmuInspectionError: If the FMU cannot be read or validated.
    """
    if not os.path.exists(path):
        raise FmuInspectionError(f"FMU file not found: {path}")

    if not path.endswith(".fmu"):
        raise FmuInspectionError(f"File is not an FMU (expected .fmu extension): {path}")

    # Fork-based parsing via pyssp_standard FMU context manager
    try:
        with FMU(path, mode='r') as fmu:
            md = fmu.model_description
            # Detect missing modelDescription.xml (md.path won't exist)
            if not md.path.exists():
                raise FmuInspectionError(f"FMU {path}: missing modelDescription.xml")
            doc = md.load_document()
    except FmuInspectionError:
        raise
    except Exception as e:
        msg = str(e)
        if "BadZipFile" in type(e).__name__ or "not a zip file" in msg.lower():
            raise FmuInspectionError(f"FMU {path}: not a valid ZIP archive") from e
        if "ParseError" in type(e).__name__:
            raise FmuInspectionError(f"FMU {path}: invalid modelDescription.xml: {e}") from e
        raise FmuInspectionError(f"Failed to read FMU {path}: {e}") from e

    # Validate FMI version
    if doc.fmi_version != "2.0":
        raise FmuInspectionError(
            f"FMU {path}: unsupported FMI version '{doc.fmi_version}', expected '2.0'"
        )

    # Validate that this is a ModelExchange FMU
    if doc.interface_type != "ModelExchange":
        raise FmuInspectionError(
            f"FMU {path}: not a ModelExchange FMU (found type: {doc.interface_type})"
        )

    # Build ScalarVariable dict from fork's typed dataclass attributes
    interface_attrs = doc.interface_attributes
    variables: Dict[str, ScalarVariable] = {}
    for var in doc.variables:
        # value_reference is str for FMI 2.0; cast to int for downstream
        vr = int(var.value_reference) if var.value_reference else 0

        # start is str | None; convert to float for ScalarVariable model
        start_val: Optional[float] = None
        if var.start is not None:
            try:
                start_val = float(var.start)
            except (ValueError, TypeError):
                start_val = None

        # unit is in type_attributes dict for the fork
        unit: Optional[str] = None
        if var.type_attributes:
            unit = var.type_attributes.get("unit")

        # type_name is already "Real", "Integer", etc. (full names, not "TypeReal")
        type_name = var.type_name

        sv = ScalarVariable(
            name=var.name,
            value_reference=vr,
            type=type_name,
            causality=var.causality or "local",
            variability=var.variability or "continuous",
            description=var.description,
            unit=unit,
            start=start_val,
        )
        variables[sv.name] = sv

    # ModelIdentifier from interface_attributes (ModelExchange element attributes)
    model_identifier = interface_attrs.get("modelIdentifier", "")

    # Capability flags from interface_attributes
    has_capabilities = bool(model_identifier)
    can_get_and_set_state = interface_attrs.get("canGetAndSetState", "false").lower() == "true"
    can_serialize_fmu_state = interface_attrs.get("canSerializeFMUstate", "false").lower() == "true"
    can_get_directional_derivative = (
        interface_attrs.get("providesDirectionalDerivative", "false").lower() == "true"
    )

    # Count continuous states and event indicators
    n_continuous_states = int(interface_attrs.get("numberOfContinuousStates", "0"))
    n_event_indicators = int(interface_attrs.get("numberOfEventIndicators", "0"))

    # Detect unsupported features
    unsupported: List[str] = []
    can_gs = interface_attrs.get("canGetAndSetFMUstate", "false")
    if can_gs.lower() == "false":
        unsupported.append("FMU does not support get/set state")
    if n_event_indicators > 0:
        unsupported.append(f"FMU has {n_event_indicators} event indicators (event handling limited)")

    # Root-level attributes (description, author, version are not direct fields)
    root_attrs = doc.root.attributes if doc.root else {}

    return FmuMetadata(
        model_identifier=model_identifier,
        fmi_version="2.0",
        guid=doc.guid,
        model_name=doc.model_name,
        description=root_attrs.get("description", ""),
        author=root_attrs.get("author", ""),
        version=root_attrs.get("version", ""),
        generation_tool=doc.generation_tool or "",
        generation_date_and_time=doc.generation_date_and_time or "",
        variables=variables,
        n_continuous_states=n_continuous_states,
        n_event_indicators=n_event_indicators,
        has_capabilities=has_capabilities,
        can_get_and_set_state=can_get_and_set_state,
        can_serialize_fmu_state=can_serialize_fmu_state,
        can_get_directional_derivative=can_get_directional_derivative,
        unsupported=unsupported,
    )
