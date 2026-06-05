"""CMakeLists.txt generation for the wrapper build system."""
from __future__ import annotations

from typing import List

from cs_fmu_packager.models import MappingTable, PackageSpec


def generate_cmake(mapping: MappingTable, spec: PackageSpec) -> str:
    """Generate CMakeLists.txt content.

    Args:
        mapping: Resolved mapping table.
        spec: Package spec (for FMU count/name).

    Returns:
        CMakeLists.txt content as a string.
    """
    # Collect all source files
    source_files: List[str] = [
        "fmi2_interface.c",
        "solver_integration.c",
        "fixed_point_iteration.c",
    ]

    sources_str = "    ".join(f"${{CMAKE_CURRENT_SOURCE_DIR}}/{s}\n" for s in source_files)

    fmu_name = spec.metadata.get("identifier", "cs_fmu")

    return f"""cmake_minimum_required(VERSION 3.22)
project({fmu_name}_wrapper LANGUAGES C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

# Find SUNDIALS dependencies
find_package(SUNDIALS REQUIRED COMPONENTS arkode nvecserial)

# Include FMI 2.0 standard headers
set(FMI_HEADERS_DIR "${{CMAKE_CURRENT_SOURCE_DIR}}/c_headers")
set(WRAPPER_HEADERS_DIR "${{CMAKE_CURRENT_SOURCE_DIR}}/src/cs_fmu_packager/codegen")

# Source files
set(SOURCES
    {sources_str})

# Build shared library
add_library({fmu_name} SHARED ${{SOURCES}})

target_include_directories({fmu_name} PRIVATE
    ${{FMI_HEADERS_DIR}}
    ${{WRAPPER_HEADERS_DIR}}
    ${{SUNDIALS_INCLUDE_DIRS}}
)

target_link_libraries({fmu_name} PRIVATE
    SUNDIALS::arkode
    SUNDIALS::nvecserial
)

# Output to binaries/linux64/
set_target_properties({fmu_name} PROPERTIES
    LIBRARY_OUTPUT_DIRECTORY "${{CMAKE_BINARY_DIR}}/binaries/linux64"
    PREFIX ""
)

# Platform checks
if(NOT UNIX)
    message(FATAL_ERROR "Only Linux is supported (v1 constraint)")
endif()
"""


def generate_model_description_xml(mapping: MappingTable, spec: PackageSpec) -> str:
    """Generate modelDescription.xml for the packaged Co-Simulation FMU."""
    from xml.sax.saxutils import escape

    fmu_name = spec.metadata.get("identifier", "cs_fmu")
    fmu_guid = spec.metadata.get("guid", _derive_guid(spec))
    description = spec.metadata.get("description", f"Packaged Co-Simulation FMU: {fmu_name}")
    author = spec.metadata.get("author", "cs-fmu-packager")
    version = spec.metadata.get("version", "0.1.0")
    generator = f"cs-fmu-packager {version}"
    generator_tool = f"cs-fmu-packager {version}"

    # Collect all wrapper variables
    xml_vars = []
    for var in mapping.all_variables():
        start_attr = ""
        if var.start is not None:
            start_attr = ' start="{}"'.format(var.start)
        unit_attr = ""
        if var.unit:
            unit_attr = ' unit="{}"'.format(escape(var.unit))
        desc = escape(var.description or "")
        var_xml = (
            '\n'
            '      <ScalarVariable\n'
            '        name="{}"\n'
            '        valueReference="{}"\n'
            '        description="{}"\n'
            '        causality="{}"\n'
            '        variability="{}"\n'
            '      >\n'
            '        <Real{}{}\n'
            '        />\n'
            '      </ScalarVariable>'
        ).format(
            escape(var.wrapper_name),
            _vr_for_var(mapping, var),
            desc,
            var.causality,
            _variability_for_causality(var.causality),
            start_attr,
            unit_attr,
        )
        xml_vars.append(var_xml)

    variables_section = "\n".join(xml_vars)

    # Capability flags for CoSimulation
    can_handle_variable_step = "false"
    can_interpolate = "false"

    # List internal FMUs for annotation
    internal_fmus = ", ".join(sorted(spec.fmus.keys()))
    solver_type = spec.solver.type
    num_algebraic_loops = len(mapping.algebraic_loops)

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<fmiModelDescription
  fmiVersion="2.0"
  modelName="{escape(fmu_name)}"
  guid="{escape(fmu_guid)}"
  description="{escape(description)}"
  author="{escape(author)}"
  version="{escape(version)}"
  generationTool="{escape(generator_tool)}"
  generationDateAndTime="{_now_iso()}"
  variableNamingConvention="structured"
  numberOfEventIndicators="0"
>
  <CoSimulation
    modelIdentifier="{escape(fmu_name)}"
    canHandleVariableCommunicationStepSize="{can_handle_variable_step}"
    canInterpolateInputs="{can_interpolate}"
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
            solverType="{escape(solver_type)}"
            solverStepSize="{spec.solver.step_size}"
            communicationStepSize="{spec.wrapper.communication_step}"
            internalFMUs="{escape(internal_fmus)}"
            algebraicLoopCount="{num_algebraic_loops}"
            algebraicLoopMaxIterations="{spec.solver.algebraic_loop.max_iterations}"
            algebraicLoopTolerance="{spec.solver.algebraic_loop.tolerance}"
          />
          <InternalConnections>
            {_generate_connections_xml(mapping)}
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
      {_generate_outputs_xml(mapping)}
    </Outputs>
    <InitialUnknowns>
    </InitialUnknowns>
  </ModelStructure>
</fmiModelDescription>
"""


def _vr_for_var(mapping: MappingTable, var) -> int:
    """Generate a deterministic value reference for a wrapper variable."""
    # Use a hash of the wrapper variable name to get a unique VR
    import hashlib
    h = hashlib.md5(var.wrapper_name.encode())
    return int(h.hexdigest()[:8], 16) % 100000


def _variability_for_causality(causality: str) -> str:
    if causality == "parameter":
        return "parameter"
    elif causality == "input":
        return "continuous"
    elif causality == "output":
        return "continuous"
    return "continuous"


def _derive_guid(spec: PackageSpec) -> str:
    """Derive a deterministic GUID from spec content."""
    import hashlib
    content = str(sorted(spec.fmus.keys())) + str(spec.solver.step_size)
    h = hashlib.md5(content.encode())
    raw = h.digest()
    # Format as GUID: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
    def _to_hex(b):
        return ''.join(f'{c:02x}' for c in b)
    return f"{_to_hex(raw[:4])}-{_to_hex(raw[4:6])}-{_to_hex(raw[6:8])}-{_to_hex(raw[8:10])}-{_to_hex(raw[10:16])}"


def _now_iso() -> str:
    """Generate ISO timestamp for generation date."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _generate_connections_xml(mapping: MappingTable) -> str:
    lines = []
    for conn in mapping.connections:
        lines.append(
            f'            <Connection source="{conn.source_fmu}.{conn.source_variable}" '
            f'target="{conn.target_fmu}.{conn.target_variable}" />'
        )
    return "\n".join(lines)


def _generate_outputs_xml(mapping: MappingTable) -> str:
    lines = []
    for var in mapping.wrapper_outputs:
        lines.append(
            f'      <Unknown index="{_vr_for_var(mapping, var)}" '
            f'dependencies="" />'
        )
    return "\n".join(lines)