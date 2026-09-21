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
find_package(SUNDIALS REQUIRED COMPONENTS arkode cvode sunlinsoldense sunmatrixdense nvecserial)

# Include FMI 2.0 standard headers
set(FMI_HEADERS_DIR "${{CMAKE_CURRENT_SOURCE_DIR}}")
set(WRAPPER_HEADERS_DIR "${{CMAKE_CURRENT_SOURCE_DIR}}")

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
    SUNDIALS::cvode
    SUNDIALS::sunlinsoldense
    SUNDIALS::sunmatrixdense
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