"""SSP package specification parsing and normalization.

Reads a complete SSP package (``.ssp``) — a ZIP archive containing
``SystemStructure.ssd`` and the embedded FMU resources — validates it,
extracts the embedded internal FMUs into a caller-owned workspace
directory, and normalizes the whole package into a ``PackageSpec``.

The parsing delegates XML handling to the ``pyssp_standard`` SSP 1.0
stack (``Ssp1SsdCodec``); this module provides the normalization layer
from ``Ssd1SystemStructureDescription`` to the packaging pipeline's
``PackageSpec`` dataclass.
"""

from __future__ import annotations

import os
import tempfile
import weakref
import zipfile
from typing import Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET

from pyssp_standard.standard.ssp1.codec.ssd_codec import Ssp1SsdCodec
from pyssp_standard.standard.ssp1.codec.xml_utils import NS_SSD
from pyssp_standard.standard.ssp1.model.ssd_model import (
    Ssd1Component,
    Ssd1Connection,
    Ssd1Connector,
    Ssd1SystemStructureDescription,
)

from cs_fmu_packager.errors import SpecValidationError
from cs_fmu_packager.models import (
    AlgebraicLoopConfig,
    Connection,
    FmuRef,
    PackageSpec,
    SOLVER_TYPE_ENUM,
    SolverConfig,
    WrapperConfig,
    WrapperVariable,
)

_SYSTEM_STRUCTURE_ENTRY = "SystemStructure.ssd"

# MIME type of an FMU component in an SSD (SSP 1.0 default).
_FMU_COMPONENT_TYPE = "application/x-fmu-sharedlibrary"

# Vendor annotation that carries the cs-fmu-packager solver/wrapper policy.
_VENDOR_ANNOTATION_TYPE = "cs-fmu-packager"

_VALID_TYPES = ("Real", "Integer", "Boolean", "String")

# SSP 1.0 connector kinds -> wrapper variable causality.
_KIND_TO_CAUSALITY = {
    "input": "input",
    "output": "output",
    "parameter": "parameter",
    "calculatedParameter": "output",
    "inout": "input",
}


# ---------------------------------------------------------------------------
# Tolerant XML parsing
# ---------------------------------------------------------------------------


def _remap_namespace(element: ET.Element, namespace: str) -> None:
    """Rewrite element and child tags to live in *namespace* in place."""
    element.tag = f"{{{namespace}}}{element.tag.rsplit('}', 1)[-1]}"
    for child in element:
        _remap_namespace(child, namespace)


def _parse_ssd(xml_text: str) -> Ssd1SystemStructureDescription:
    """Parse an SSD XML document tolerating root/namespace variants.

    The installed ``pyssp_standard`` codec is namespace-strict on the SSD
    namespace (``http://ssp-standard.org/SSP1/SystemStructureDescription``).
    Canonical SSP 1.0 documents may use a different root (``SystemStructure``)
    and namespace; this normalizes such documents onto the codec's namespace
    before delegation.
    """
    root = ET.fromstring(xml_text)
    if root.tag != f"{{{NS_SSD}}}SystemStructureDescription":
        _remap_namespace(root, NS_SSD)
    root.set("name", root.get("name", "system"))
    root.set("version", root.get("version", "1.0"))
    return Ssp1SsdCodec().parse(ET.tostring(root, encoding="unicode"))


# ---------------------------------------------------------------------------
# Vendor configuration annotation
# ---------------------------------------------------------------------------


def _coerce_config(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise SpecValidationError(f"{name}: must be a positive number, got {value}")
    return float(value)


def _opt_float(attrs, key: str, default: float) -> float:
    if key not in attrs:
        return default
    try:
        return _coerce_config(float(attrs[key]), key)
    except (TypeError, ValueError):
        raise SpecValidationError(f"{key}: must be a positive number, got {attrs[key]}")


def _opt_int(attrs, key: str, default: int) -> int:
    if key not in attrs:
        return default
    try:
        value = int(attrs[key])
    except (TypeError, ValueError):
        raise SpecValidationError(
            f"{key}: must be a positive integer, got {attrs[key]}"
        )
    if value <= 0:
        raise SpecValidationError(f"{key}: must be a positive integer, got {value}")
    return value


def _parse_vendor_config(annotations) -> Tuple[SolverConfig, WrapperConfig]:
    """Read solver/wrapper policy from the vendor annotation.

    Falls back to the packaging defaults when no ``cs-fmu-packager``
    annotation is present.
    """
    solver = SolverConfig()
    wrapper = WrapperConfig()

    for annotation in annotations:
        if annotation.type_name != _VENDOR_ANNOTATION_TYPE:
            continue
        for element in annotation.elements:
            name = element.tag.rsplit("}", 1)[-1]
            attrs = element.attrib
            if name == "Solver":
                solver_type = attrs.get("type", solver.type)
                if solver_type not in SOLVER_TYPE_ENUM:
                    raise SpecValidationError(
                        f"solver type must be one of {sorted(SOLVER_TYPE_ENUM)} "
                        f"(v1 constraint), got '{solver_type}'"
                    )
                solver.type = solver_type
                solver.step_size = _opt_float(attrs, "stepSize", solver.step_size)
                solver.tolerance = _opt_float(attrs, "tolerance", solver.tolerance)
                solver.communication_step = _opt_float(
                    attrs, "communicationStep", solver.communication_step
                )
            elif name == "AlgebraicLoop":
                solver.algebraic_loop = AlgebraicLoopConfig(
                    max_iterations=_opt_int(attrs, "maxIterations", 100),
                    tolerance=_opt_float(attrs, "tolerance", 1e-6),
                )
            elif name == "Wrapper":
                wrapper.communication_step = _opt_float(
                    attrs, "communicationStep", wrapper.communication_step
                )
    return solver, wrapper


# ---------------------------------------------------------------------------
# Parameter start values
# ---------------------------------------------------------------------------


def _coerce_parameter_value(parameter) -> Optional[object]:
    """Convert an ``Ssp1Parameter`` value string to a typed Python value."""
    raw = parameter.attributes.get("value")
    if raw is None:
        return None
    try:
        if parameter.type_name == "Integer":
            return int(raw)
        if parameter.type_name == "Boolean":
            return raw.strip().lower() == "true"
        if parameter.type_name == "String":
            return raw
        return float(raw)
    except (TypeError, ValueError):
        return None


def _parameter_value_map(system) -> Dict[str, object]:
    """Flatten top-level System ParameterValues into ``name -> value``."""
    values: Dict[str, object] = {}
    for binding in system.parameter_bindings or []:
        if binding.parameter_set is None:
            continue
        for parameter in binding.parameter_set.parameters:
            value = _coerce_parameter_value(parameter)
            if value is not None:
                values[parameter.name] = value
    return values


def _lookup_parameter(binding_values: Dict[str, object], component: str, variable: str):
    """Resolve a start value for ``component/variable`` from parameter values."""
    for candidate in (
        f"{component}/{variable}",
        f"{component}.{variable}",
        f"/{component}/{variable}",
        variable,
    ):
        if candidate in binding_values:
            return binding_values[candidate]
    return None


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------


def _normalize_member_path(source: str) -> str:
    """Normalize a relative ``source`` URI to a ZIP member path."""
    path = source.replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    return path.lstrip("/")


def _extract_fmu(
    archive: zipfile.ZipFile,
    component: Ssd1Component,
    workspace_dir: str,
    errors: List[str],
) -> Optional[FmuRef]:
    """Extract an embedded FMU component from the archive into the workspace."""
    name = component.name or ""
    if not name:
        errors.append("component: missing required attribute 'name'")
        return None

    if component.component_type not in (None, _FMU_COMPONENT_TYPE):
        errors.append(
            f"component '{name}'.type: unsupported type "
            f"'{component.component_type}' (expected '{_FMU_COMPONENT_TYPE}')"
        )

    source = component.source or ""
    member = _normalize_member_path(source)
    if not member:
        errors.append(f"component '{name}': missing required attribute 'source'")
        return None
    if member not in archive.namelist():
        errors.append(
            f"component '{name}' source '{source}': member not found in the "
            ".ssp archive"
        )
        return None

    try:
        data = archive.read(member)
    except (KeyError, zipfile.BadZipFile) as e:
        errors.append(f"component '{name}' source '{source}': failed to read: {e}")
        return None

    target = os.path.join(workspace_dir, f"{name}.fmu")
    try:
        with open(target, "wb") as f:
            f.write(data)
    except OSError as e:
        errors.append(f"component '{name}': failed to extract: {e}")
        return None

    return FmuRef(name=name, path=target, fmi_version="2.0", kind="ModelExchange")


def _normalize_connection(
    conn: Ssd1Connection,
    fmu_keys: set,
    errors: List[str],
) -> Optional[Connection]:
    """Normalize an SSD connection into a packaging ``Connection``."""
    if not conn.start_element or not conn.end_element:
        errors.append(
            "connection: system-level (boundary) connections are not supported; "
            "wire boundary variables through system connectors instead"
        )
        return None
    if not conn.start_connector or not conn.end_connector:
        errors.append(
            f"connection {conn.start_element}->{conn.end_element}: "
            "missing connector name"
        )
        return None

    if conn.start_element not in fmu_keys:
        errors.append(
            f"connection: start element '{conn.start_element}' not defined "
            "as a component"
        )
    if conn.end_element not in fmu_keys:
        errors.append(
            f"connection: end element '{conn.end_element}' not defined "
            "as a component"
        )
    return Connection(
        source_fmu=conn.start_element,
        source_variable=conn.start_connector,
        target_fmu=conn.end_element,
        target_variable=conn.end_connector,
    )


def _split_element_path(element: Optional[str]) -> Optional[Tuple[str, str]]:
    """Split a connector ``element`` path into ``(component, variable)``."""
    if not element:
        return None
    parts = element.lstrip("/").split("/", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        return None
    return (parts[0], parts[1])


def _normalize_connector(
    connector: Ssd1Connector,
    binding_values: Dict[str, object],
    fmu_keys: set,
    seen_names: set,
    errors: List[str],
) -> Optional[WrapperVariable]:
    """Normalize a system-level connector into a boundary ``WrapperVariable``."""
    name = connector.name
    if not name:
        errors.append("connector: missing required attribute 'name'")
        return None
    if name in seen_names:
        errors.append(f"connector '{name}': duplicate boundary variable name")
        return None
    seen_names.add(name)

    causality = _KIND_TO_CAUSALITY.get(connector.kind)
    if causality is None:
        errors.append(
            f"connector '{name}': unsupported kind '{connector.kind}' "
            f"(expected one of {sorted(_KIND_TO_CAUSALITY)})"
        )
        return None

    var_type = connector.type_name or "Real"
    if var_type not in _VALID_TYPES:
        errors.append(
            f"connector '{name}': type must be one of {_VALID_TYPES}, "
            f"got '{var_type}'"
        )
        return None

    element = _split_element_path(connector.element)
    if element is None:
        errors.append(
            f"connector '{name}': invalid 'element' path "
            f"'{connector.element}', expected '<component>/<variable>'"
        )
        return None
    component, variable = element
    if component not in fmu_keys:
        errors.append(
            f"connector '{name}': element FMU '{component}' not defined "
            "as a component"
        )
        return None

    start = _lookup_parameter(binding_values, component, variable)
    unit = connector.type_attributes.get("unit") if connector.type_attributes else None

    if causality == "output":
        source_fmu, source_variable = component, variable
        target_fmu = target_variable = None
    else:
        source_fmu = source_variable = None
        target_fmu, target_variable = component, variable

    return WrapperVariable(
        name=name,
        type=var_type,
        causality=causality,
        source_fmu=source_fmu,
        source_variable=source_variable,
        target_fmu=target_fmu,
        target_variable=target_variable,
        start=start,
        description=connector.description or "",
        unit=unit,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_spec(path: str, workspace_dir: Optional[str] = None) -> PackageSpec:
    """Parse and validate a complete SSP package (``.ssp``).

    Args:
        path: Path to the ``.ssp`` archive containing ``SystemStructure.ssd``
            and the embedded internal FMUs.
        workspace_dir: Directory into which the embedded FMUs are extracted.
            It must be owned and cleaned up by the caller (the CLI, or a
            test). When *None*, a temporary directory is created for the
            lifetime of the returned ``PackageSpec`` (registered through
            ``weakref`` for best-effort cleanup).

    Returns:
        A validated PackageSpec instance whose ``FmuRef.path`` values point
        at the extracted FMUs inside ``workspace_dir``.

    Raises:
        SpecValidationError: If the SSP file cannot be read or validation fails.
    """
    if not os.path.exists(path):
        raise SpecValidationError(f"SSP file not found: {path}")
    if not path.endswith(".ssp"):
        raise SpecValidationError(
            f"Expected a complete SSP package ('.ssp'), got: {path}"
        )

    try:
        archive = zipfile.ZipFile(path, "r")
    except (zipfile.BadZipFile, OSError) as e:
        raise SpecValidationError(f"Failed to open SSP archive: {e}") from e

    try:
        if _SYSTEM_STRUCTURE_ENTRY not in archive.namelist():
            raise SpecValidationError(
                f"SSP archive '{path}' is missing '{_SYSTEM_STRUCTURE_ENTRY}'"
            )
        xml_text = archive.read(_SYSTEM_STRUCTURE_ENTRY).decode("utf-8", "replace")
        document = _parse_ssd(xml_text)
    except SpecValidationError:
        raise
    except Exception as e:
        raise SpecValidationError(f"Failed to parse SystemStructure.ssd: {e}") from e

    if document.system is None:
        raise SpecValidationError(f"SSP '{path}': no <System> element found")

    try:
        spec = _normalize_document(document, archive, workspace_dir)
    finally:
        archive.close()

    return spec


def _normalize_document(
    document: Ssd1SystemStructureDescription,
    archive: zipfile.ZipFile,
    workspace_dir: Optional[str],
) -> PackageSpec:
    system = document.system
    errors: List[str] = []

    own_workspace = None
    if workspace_dir is None:
        own_workspace = tempfile.TemporaryDirectory(prefix="cs_fmu_ssp_")
        workspace_dir = own_workspace.name
    os.makedirs(workspace_dir, exist_ok=True)

    # Components -> FmuRef (extract embedded FMUs into the workspace).
    fmu_refs: Dict[str, FmuRef] = {}
    fmu_keys: set = set()
    for component in system.elements:
        if not isinstance(component, Ssd1Component):
            errors.append(
                "nested <System> elements are not supported in v1; "
                "only FMU components at the top level"
            )
            continue
        ref = _extract_fmu(archive, component, workspace_dir, errors)
        if ref is not None:
            fmu_refs[ref.name] = ref
            fmu_keys.add(ref.name)

    # Connections -> Connection.
    connections: List[Connection] = []
    for conn in system.connections:
        normalized = _normalize_connection(conn, fmu_keys, errors)
        if normalized is not None:
            connections.append(normalized)

    # System connectors -> boundary WrapperVariables.
    binding_values = _parameter_value_map(system)
    variables: List[WrapperVariable] = []
    seen_names: set = set()
    for connector in system.connectors:
        normalized = _normalize_connector(
            connector, binding_values, fmu_keys, seen_names, errors
        )
        if normalized is not None:
            variables.append(normalized)

    # Vendor configuration annotation (or defaults).
    solver, wrapper = _parse_vendor_config(document.metadata.annotations)

    if solver.step_size > solver.communication_step:
        errors.append(
            f"solver.step_size ({solver.step_size}) must be <= "
            f"solver.communication_step ({solver.communication_step})"
        )
    if abs(solver.communication_step - wrapper.communication_step) > 1e-15:
        errors.append(
            f"solver.communication_step ({solver.communication_step}) must equal "
            f"wrapper.communication_step ({wrapper.communication_step})"
        )

    if errors:
        raise SpecValidationError("\n".join(errors))

    metadata = {"identifier": document.name or "cs_fmu"}
    if document.metadata.description:
        metadata["description"] = document.metadata.description
    if document.metadata.author:
        metadata["author"] = document.metadata.author
    if document.metadata.fileversion:
        metadata["version"] = document.metadata.fileversion

    spec = PackageSpec(
        metadata=metadata,
        fmus=fmu_refs,
        connections=connections,
        variables=variables,
        solver=solver,
        wrapper=wrapper,
    )
    if own_workspace is not None:
        weakref.finalize(spec, own_workspace.cleanup)
    return spec