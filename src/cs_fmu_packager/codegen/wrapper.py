"""Main code generation orchestrator.

Coordinates generation of all C source files, CMakeLists.txt,
and modelDescription.xml from the resolved mapping table.
"""

from __future__ import annotations

import os
from typing import Dict

from cs_fmu_packager.codegen.cmake import generate_cmake
from cs_fmu_packager.codegen.fmi_interface import generate_fmi_interface_impl
from cs_fmu_packager.codegen.fixed_point import generate_fixed_point_impl
from cs_fmu_packager.codegen.solver import generate_solver_impl
from cs_fmu_packager.errors import CodegenError
from cs_fmu_packager.model_description import generate_model_description
from cs_fmu_packager.models import MappingTable, PackageSpec


def generate_all(
    spec: PackageSpec,
    mapping: MappingTable,
    output_dir: str,
    c_headers_dir: str,
) -> Dict[str, str]:
    """Generate all source files for the wrapper build.

    Args:
        spec: The package specification.
        mapping: The resolved mapping table.
        output_dir: Directory to write generated files into.
        c_headers_dir: Directory containing FMI C headers.

    Returns:
        Dict mapping generated file paths to their content (for testing).

    Raises:
        CodegenError: If code generation fails.
    """
    generated: Dict[str, str] = {}

    os.makedirs(output_dir, exist_ok=True)

    try:
        # Generate CMakeLists.txt
        cmake_content = generate_cmake(mapping, spec)
        cmake_path = os.path.join(output_dir, "CMakeLists.txt")
        with open(cmake_path, "w") as f:
            f.write(cmake_content)
        generated[cmake_path] = cmake_content

        # Generate modelDescription.xml
        model_desc_content = generate_model_description(spec, mapping)
        model_desc_path = os.path.join(output_dir, "modelDescription.xml")
        with open(model_desc_path, "w") as f:
            f.write(model_desc_content)
        generated[model_desc_path] = model_desc_content

        # Generate fmi2_interface.c
        fmi_impl = generate_fmi_interface_impl(spec, mapping)
        fmi_path = os.path.join(output_dir, "fmi2_interface.c")
        with open(fmi_path, "w") as f:
            f.write(fmi_impl)
        generated[fmi_path] = fmi_impl

        # Generate solver_integration.c
        solver_impl = generate_solver_impl(spec, mapping)
        solver_path = os.path.join(output_dir, "solver_integration.c")
        with open(solver_path, "w") as f:
            f.write(solver_impl)
        generated[solver_path] = solver_impl

        # Generate fixed_point_iteration.c
        fixed_impl = generate_fixed_point_impl(spec, mapping)
        fixed_path = os.path.join(output_dir, "fixed_point_iteration.c")
        with open(fixed_path, "w") as f:
            f.write(fixed_impl)
        generated[fixed_path] = fixed_impl

        # Copy C headers into build dir
        required_headers = ("fmi2Functions.h", "fmi2TypesPlatform.h", "fmi2FunctionTypes.h")
        missing_headers: list[str] = []
        for hdr in required_headers:
            src = os.path.join(c_headers_dir, hdr)
            if not os.path.exists(src):
                missing_headers.append(hdr)
                continue
            dst = os.path.join(output_dir, hdr)
            with open(src, "r") as f_in:
                content = f_in.read()
            with open(dst, "w") as f_out:
                f_out.write(content)
            generated[dst] = content

        if missing_headers:
            raise CodegenError(
                f"Missing required FMI 2.0 header file(s) in '{c_headers_dir}': "
                f"{', '.join(missing_headers)}. "
                f"Ensure the package is properly installed or use --c-headers to "
                f"specify a directory containing all required headers."
            )

        # Copy codegen headers into build dir
        codegen_dir = os.path.dirname(__file__)
        for hdr_file in os.listdir(codegen_dir):
            if hdr_file.endswith(".h"):
                src = os.path.join(codegen_dir, hdr_file)
                dst = os.path.join(output_dir, hdr_file)
                with open(src, "r") as f_in:
                    content = f_in.read()
                with open(dst, "w") as f_out:
                    f_out.write(content)
                generated[dst] = content

    except OSError as e:
        raise CodegenError(f"Failed to write generated files: {e}") from e

    return generated