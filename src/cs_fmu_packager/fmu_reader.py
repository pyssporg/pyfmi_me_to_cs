"""FMU inspection and modelDescription.xml parser.

Opens an FMI 2.0 Model Exchange FMU archive, validates its structure,
and extracts all metadata from modelDescription.xml.
"""

from __future__ import annotations

import os
import zipfile
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional

from cs_fmu_packager.errors import FmuInspectionError
from cs_fmu_packager.models import FmuMetadata, ScalarVariable


def _parse_scalar_variables(root: ET.Element) -> Dict[str, ScalarVariable]:
    """Parse all ScalarVariable elements from modelDescription.xml."""
    variables: Dict[str, ScalarVariable] = {}
    ns = {"fmi": "http://www.modelisar.com/schema/fmi2"}
    # Try without namespace first (some FMUs omit namespace)
    scalar_vars = root.findall(".//ScalarVariable")
    if not scalar_vars:
        scalar_vars = root.findall(".//fmi:ScalarVariable", ns)

    for sv in scalar_vars:
        name = sv.get("name", "")
        vr = int(sv.get("valueReference", 0))
        causality = sv.get("causality", "local")
        variability = sv.get("variability", "continuous")
        desc = sv.get("description")

        # Determine the variable type sub-element (Real, Integer, Boolean, String)
        var_type = "Real"
        unit = None
        start = None

        for child in sv:
            tag = child.tag
            if "}" in tag:
                tag = tag.split("}", 1)[1]
            if tag in ("Real", "Integer", "Boolean", "String"):
                var_type = tag
                unit = child.get("unit") or child.get("unit_") or None
                start_str = child.get("start")
                if start_str is not None:
                    try:
                        start = float(start_str)
                    except ValueError:
                        pass
                break

        sv_obj = ScalarVariable(
            name=name,
            value_reference=vr,
            type=var_type,
            causality=causality,
            variability=variability,
            description=desc,
            unit=unit,
            start=start,
        )
        variables[name] = sv_obj

    return variables


def _detect_unsupported_features(root: ET.Element) -> List[str]:
    """Detect features the wrapper does not support."""
    unsupported: List[str] = []
    ns = {"fmi": "http://www.modelisar.com/schema/fmi2"}
    me = root.find("fmi:ModelExchange", ns)
    if me is None:
        me = root.find("ModelExchange")

    if me is not None:
        # Check for variable-step solver requirement
        can_interpolate_inputs = me.get("canInterpolateInputs", "false")
        # There's no standard flag for "requires variable-step" but we check
        # the completed integrator step capability
        can_handle_variable_step = me.get("completedIntegratorStepNotNeeded", "false")
        # If the FMU does NOT support getting/setting state,
        # we're more limited in event handling
        can_get_set_state = me.get("canGetAndSetFMUstate", "false")
        if can_get_set_state == "false":
            unsupported.append("FMU does not support get/set state")

    # Check if there are any event indicators (zero-crossing signals)
    # This would indicate event-driven behavior
    num_event_indicators = root.get("numberOfEventIndicators", "0")
    if num_event_indicators and int(num_event_indicators) > 0:
        unsupported.append(f"FMU has {num_event_indicators} event indicators (event handling limited)")

    return unsupported


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

    try:
        with zipfile.ZipFile(path, "r") as zf:
            # Validate FMU structure
            contents = set(zf.namelist())
            if "modelDescription.xml" not in contents:
                raise FmuInspectionError(f"FMU {path}: missing modelDescription.xml")

            # Read modelDescription.xml
            with zf.open("modelDescription.xml") as f:
                tree = ET.parse(f)
            root = tree.getroot()
    except zipfile.BadZipFile:
        raise FmuInspectionError(f"FMU {path}: not a valid ZIP archive")
    except ET.ParseError as e:
        raise FmuInspectionError(f"FMU {path}: invalid modelDescription.xml: {e}")

    # Extract basic metadata
    fmi_version = root.get("fmiVersion", "")
    if fmi_version != "2.0":
        raise FmuInspectionError(
            f"FMU {path}: unsupported FMI version '{fmi_version}', expected '2.0'"
        )

    guid = root.get("guid", "")
    model_name = root.get("modelName", "")

    # Determine model types
    model_types: List[str] = []
    for child in root:
        tag = child.tag
        if "}" in tag:
            tag = tag.split("}", 1)[1]
        if tag == "ModelExchange":
            model_types.append("ModelExchange")
        elif tag == "CoSimulation":
            model_types.append("CoSimulation")

    if "ModelExchange" not in model_types:
        raise FmuInspectionError(
            f"FMU {path}: not a ModelExchange FMU (found types: {model_types})"
        )

    # Parse capability flags
    me_elem = root.find("ModelExchange")
    if me_elem is None:
        for child in root:
            tag = child.tag
            if "}" in tag:
                tag = tag.split("}", 1)[1]
            if tag == "ModelExchange":
                me_elem = child
                break

    can_get_set_state = False
    can_serialize = False
    can_provide_directional = False
    model_identifier = ""
    if me_elem is not None:
        model_identifier = me_elem.get("modelIdentifier", "")
        can_get_set_state = me_elem.get("canGetAndSetFMUstate", "false").lower() == "true"
        can_serialize = me_elem.get("canSerializeFMUstate", "false").lower() == "true"
        can_provide_directional = me_elem.get("providesDirectionalDerivatives", "false").lower() == "true"

    # Parse variables
    variables = _parse_scalar_variables(root)
    variables_by_ref: Dict[int, ScalarVariable] = {}
    for var in variables.values():
        variables_by_ref[var.value_reference] = var

    # Find continuous states
    continuous_states = [
        v.name for v in variables.values()
        if v.causality == "local" and v.variability == "continuous"
    ]

    # Find event indicators
    num_event_indicators_str = root.get("numberOfEventIndicators", "0")
    num_event_indicators = int(num_event_indicators_str)

    # Detect unsupported features
    unsupported = _detect_unsupported_features(root)

    return FmuMetadata(
        fmi_version=fmi_version,
        guid=guid,
        model_name=model_name,
        model_identifier=model_identifier,
        model_types=model_types,
        can_get_and_set_fmu_state=can_get_set_state,
        can_serialize_fmu_state=can_serialize,
        can_provide_directional_derivatives=can_provide_directional,
        provides_directional_derivatives=can_provide_directional,
        variables=variables,
        variables_by_ref=variables_by_ref,
        unsupported_features=unsupported,
    )