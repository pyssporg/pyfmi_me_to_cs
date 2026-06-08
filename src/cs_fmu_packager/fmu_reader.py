"""FMU inspection and modelDescription.xml parser.

Opens an FMI 2.0 Model Exchange FMU archive, validates its structure,
and extracts all metadata from modelDescription.xml.

Uses pyssp_standard for variable list discovery and lxml for metadata
that pyssp_standard doesn't parse (valueReference, modelIdentifier,
capabilities).
"""

from __future__ import annotations

import os
import zipfile
from typing import Dict, List, Optional

from lxml import etree as ET
from pyssp_standard.fmu import FMU

from cs_fmu_packager.errors import FmuInspectionError
from cs_fmu_packager.models import FmuMetadata, ScalarVariable

# FMI 2.0 namespace
FMI_NS = "http://www.modelisar.com/schema/fmi2"


def _ns_tag(tag: str, ns: Dict[str, str]) -> str:
    """Return the FMI-namespaced tag for namespace-fallback lookups."""
    return f"{{{ns['fmi']}}}{tag}"


def _find_elem(root: ET.Element, tag: str, ns: Dict[str, str]) -> Optional[ET.Element]:
    """Find an element, trying with namespace first, then without."""
    elem = root.find(_ns_tag(tag, ns), ns)
    if elem is None:
        elem = root.find(tag)
    return elem


def _iter_elems(root: ET.Element, tag: str, ns: Dict[str, str]):
    """Iterate over elements matching tag, trying with namespace first."""
    ns_tag_str = _ns_tag(tag, ns)
    found = False
    for elem in root.iter(ns_tag_str):
        found = True
        yield elem
    if not found:
        for elem in root.iter(tag):
            yield elem


def _detect_unsupported_features(root: ET.Element, ns: Dict[str, str]) -> List[str]:
    """Detect features the wrapper does not support."""
    unsupported: List[str] = []
    me = _find_elem(root, "ModelExchange", ns)

    if me is not None:
        can_get_set_state = me.get("canGetAndSetFMUstate", "false")
        if can_get_set_state == "false":
            unsupported.append("FMU does not support get/set state")

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

    # Validate ZIP structure and extract modelDescription.xml with lxml first
    # (pyssp_standard doesn't handle edge cases like missing modelDescription.xml
    # or non-FMI-2.0 content gracefully)
    try:
        with zipfile.ZipFile(path, "r") as zf:
            contents = set(zf.namelist())
            if "modelDescription.xml" not in contents:
                raise FmuInspectionError(f"FMU {path}: missing modelDescription.xml")

            with zf.open("modelDescription.xml") as f:
                tree = ET.parse(f)
            root = tree.getroot()
    except zipfile.BadZipFile:
        raise FmuInspectionError(f"FMU {path}: not a valid ZIP archive")
    except ET.ParseError as e:
        raise FmuInspectionError(f"FMU {path}: invalid modelDescription.xml: {e}")

    # Validate FMI version
    fmi_version = root.get("fmiVersion", "")
    if fmi_version != "2.0":
        raise FmuInspectionError(
            f"FMU {path}: unsupported FMI version '{fmi_version}', expected '2.0'"
        )

    # Validate that this is a ModelExchange FMU
    ns = {"fmi": FMI_NS}
    me_elem = _find_elem(root, "ModelExchange", ns)
    if me_elem is None:
        # Determine available model types for the error message
        model_types: List[str] = []
        for child in root:
            tag = child.tag
            if "}" in tag:
                tag = tag.split("}", 1)[1]
            if tag in ("ModelExchange", "CoSimulation"):
                model_types.append(tag)
        raise FmuInspectionError(
            f"FMU {path}: not a ModelExchange FMU (found types: {model_types})"
        )

    # Use pyssp_standard for variable list discovery
    try:
        with FMU(path, mode='r') as fmu:
            md = fmu.model_description
    except Exception as e:
        raise FmuInspectionError(f"Failed to read FMU {path}: {e}") from e

    # Build valueReference lookup from XML (pyssp_standard doesn't parse this)
    vr_by_name: Dict[str, int] = {}
    for sv_elem in _iter_elems(root, "ScalarVariable", ns):
        name = sv_elem.get("name", "")
        vr = int(sv_elem.get("valueReference", "0"))
        vr_by_name[name] = vr

    # Build ScalarVariable dict from pyssp_standard + valueReference lookup
    variables: Dict[str, ScalarVariable] = {}
    for pyssp_var in md.variables():
        name = pyssp_var.name
        vr = vr_by_name.get(name, 0)

        # Extract type name from pyssp_standard's type_ attribute
        type_name = pyssp_var.type_.__class__.__name__
        if type_name.startswith("Type"):
            type_name = type_name[4:]  # "TypeReal" -> "Real"

        # Extract start/unit from the type_ object
        start = None
        unit = None
        if hasattr(pyssp_var.type_, 'start'):
            start = pyssp_var.type_.start
        if hasattr(pyssp_var.type_, 'unit'):
            unit = pyssp_var.type_.unit

        sv = ScalarVariable(
            name=name,
            value_reference=vr,
            type=type_name,
            causality=pyssp_var.causality,
            variability=pyssp_var.variability,
            description=pyssp_var.description,
            unit=unit,
            start=start,
        )
        variables[sv.name] = sv

    # Extract modelIdentifier from ModelExchange element
    model_identifier = me_elem.get("modelIdentifier", "")

    # Extract capability flags from ModelExchange
    has_capabilities = False
    can_get_and_set_state = False
    can_serialize_fmu_state = False
    can_get_directional_derivative = False
    if me_elem is not None:
        has_capabilities = True
        can_get_and_set_state = me_elem.get("canGetAndSetState", "false").lower() == "true"
        can_serialize_fmu_state = me_elem.get("canSerializeFMUstate", "false").lower() == "true"
        can_get_directional_derivative = me_elem.get("providesDirectionalDerivative", "false").lower() == "true"

    # Detect unsupported features
    unsupported = _detect_unsupported_features(root, ns)

    # Count continuous states and event indicators
    n_continuous_states = 0
    n_event_indicators = 0
    if me_elem is not None:
        n_continuous_states = int(me_elem.get("numberOfContinuousStates", "0"))
        n_event_indicators = int(me_elem.get("numberOfEventIndicators", "0"))

    return FmuMetadata(
        model_identifier=model_identifier,
        fmi_version="2.0",
        guid=root.get("guid", ""),
        model_name=root.get("modelName", ""),
        description=root.get("description", ""),
        author=root.get("author", ""),
        version=root.get("version", ""),
        generation_tool=root.get("generationTool", ""),
        generation_date_and_time=root.get("generationDateAndTime", ""),
        variables=variables,
        n_continuous_states=n_continuous_states,
        n_event_indicators=n_event_indicators,
        has_capabilities=has_capabilities,
        can_get_and_set_state=can_get_and_set_state,
        can_serialize_fmu_state=can_serialize_fmu_state,
        can_get_directional_derivative=can_get_directional_derivative,
        unsupported=unsupported,
    )
