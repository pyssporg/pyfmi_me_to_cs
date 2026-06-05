"""CMake + vcpkg build integration.

Configures and runs CMake builds with vcpkg toolchain support
for compiling the generated C wrapper code.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from typing import List, Optional

from cs_fmu_packager.errors import BuildError


@dataclass
class BuildResult:
    """Result of a CMake build."""

    success: bool
    so_path: Optional[str] = None
    build_dir: str = ""
    cmake_output: str = ""
    build_output: str = ""
    arch: Optional[str] = None
    tool_versions: dict = field(default_factory=dict)


def _find_vcpkg_root(vcpkg_root_arg: Optional[str] = None) -> str:
    """Locate the vcpkg root directory.

    Resolution order:
    1. --vcpkg-root CLI argument
    2. VCPKG_ROOT environment variable
    3. Check common default locations
    """
    if vcpkg_root_arg:
        if os.path.isdir(vcpkg_root_arg):
            return vcpkg_root_arg
        raise BuildError(f"vcpkg root not found at specified path: {vcpkg_root_arg}")

    env_root = os.environ.get("VCPKG_ROOT")
    if env_root and os.path.isdir(env_root):
        return env_root

    # Check common locations
    common_paths = [
        os.path.expanduser("~/vcpkg"),
        os.path.expanduser("~/.vcpkg"),
        "/usr/local/vcpkg",
        "/opt/vcpkg",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "vcpkg"),
    ]
    for path in common_paths:
        if os.path.isdir(path):
            return path

    raise BuildError(
        "vcpkg root not found.\n"
        "\n"
        "Install vcpkg (https://github.com/microsoft/vcpkg):\n"
        "  1. git clone https://github.com/microsoft/vcpkg\n"
        "  2. cd vcpkg && ./bootstrap-vcpkg.sh (Linux)\n"
        "  3. Export VCPKG_ROOT=<cloned-path>\n"
        "  4. Run: vcpkg install sundials\n"
        "\n"
        "The following heuristic paths were checked:\n"
        + "\n".join(f"  - {p}" for p in common_paths)
        + "\n"
        "\n"
        "Set VCPKG_ROOT, install vcpkg at one of the paths above, "
        "or pass --vcpkg-root <path>."
    )


def _get_tool_versions() -> dict:
    """Capture versions of build tools for the build report."""
    versions = {}
    try:
        result = subprocess.run(
            ["cmake", "--version"], capture_output=True, text=True, timeout=10
        )
        versions["cmake"] = result.stdout.splitlines()[0] if result.stdout else "unknown"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        versions["cmake"] = "not found"

    try:
        result = subprocess.run(
            ["gcc", "--version"], capture_output=True, text=True, timeout=10
        )
        versions["gcc"] = result.stdout.splitlines()[0] if result.stdout else "unknown"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        versions["gcc"] = "not found"

    try:
        result = subprocess.run(
            [sys.executable, "--version"], capture_output=True, text=True, timeout=10
        )
        versions["python"] = result.stdout.strip() if result.stdout else "unknown"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        versions["python"] = "not found"

    return versions


def build_fmu(
    source_dir: str,
    build_dir: str,
    vcpkg_root_arg: Optional[str] = None,
    fmu_name: str = "cs_fmu",
    verbose: bool = False,
) -> BuildResult:
    """Configure and build the generated C wrapper using CMake + vcpkg.

    Args:
        source_dir: Directory containing generated source code and CMakeLists.txt.
        build_dir: Directory for CMake build artifacts.
        vcpkg_root_arg: Optional custom vcpkg root path.
        fmu_name: The FMU model identifier (used for .so output name).
        verbose: Enable verbose output.

    Returns:
        BuildResult with build status and metadata.

    Raises:
        BuildError: If build configuration or compilation fails.
    """
    vcpkg_root = _find_vcpkg_root(vcpkg_root_arg)
    toolchain_file = os.path.join(vcpkg_root, "scripts", "buildsystems", "vcpkg.cmake")

    if not os.path.exists(toolchain_file):
        raise BuildError(
            f"vcpkg toolchain file not found at {toolchain_file}. "
            f"Is vcpkg properly installed at {vcpkg_root}?"
        )

    # Ensure build directory exists
    os.makedirs(build_dir, exist_ok=True)

    tool_versions = _get_tool_versions()

    # Step 1: CMake configure
    cmake_cmd = [
        "cmake",
        "-S", source_dir,
        "-B", build_dir,
        f"-DCMAKE_TOOLCHAIN_FILE={toolchain_file}",
        "-DCMAKE_BUILD_TYPE=Release",
    ]

    if verbose:
        print(f"Configuring CMake...")
        print(f"  Source: {source_dir}")
        print(f"  Build: {build_dir}")
        print(f"  Toolchain: {toolchain_file}")

    try:
        cmake_result = subprocess.run(
            cmake_cmd, capture_output=True, text=True, timeout=300
        )
    except subprocess.TimeoutExpired:
        raise BuildError("CMake configuration timed out (300s)")
    except FileNotFoundError:
        raise BuildError("CMake not found. Is cmake installed?")

    if cmake_result.returncode != 0:
        # Capture last 50 lines of output
        output_lines = cmake_result.stdout.splitlines() + cmake_result.stderr.splitlines()
        diagnostic = "\n".join(output_lines[-50:])
        raise BuildError(
            f"CMake configuration failed:\n{diagnostic}"
        )

    if verbose:
        print("CMake configuration succeeded.")

    # Step 2: CMake build
    build_cmd = [
        "cmake",
        "--build", build_dir,
        "--config", "Release",
    ]

    try:
        build_result = subprocess.run(
            build_cmd, capture_output=True, text=True, timeout=600
        )
    except subprocess.TimeoutExpired:
        raise BuildError("CMake build timed out (600s)")

    build_output = build_result.stdout + build_result.stderr

    if build_result.returncode != 0:
        output_lines = build_output.splitlines()
        diagnostic = "\n".join(output_lines[-50:])
        raise BuildError(
            f"CMake build failed:\n{diagnostic}"
        )

    if verbose:
        print("CMake build succeeded.")

    # Step 3: Locate resulting .so
    so_path = os.path.join(build_dir, "binaries", "linux64", f"{fmu_name}.so")
    if not os.path.exists(so_path):
        # Try alternate naming (lib prefix)
        alt_so = os.path.join(build_dir, "binaries", "linux64", f"lib{fmu_name}.so")
        if os.path.exists(alt_so):
            so_path = alt_so
        else:
            # Search for any .so in binaries/linux64
            bin_dir = os.path.join(build_dir, "binaries", "linux64")
            if os.path.isdir(bin_dir):
                for f in os.listdir(bin_dir):
                    if f.endswith(".so"):
                        so_path = os.path.join(bin_dir, f)
                        break

    if not os.path.exists(so_path):
        raise BuildError(
            f"Build succeeded but .so not found at expected path: {so_path}. "
            f"Check CMake output target properties."
        )

    # Step 4: Verify architecture
    arch = None
    try:
        file_result = subprocess.run(
            ["file", so_path], capture_output=True, text=True, timeout=10
        )
        arch = file_result.stdout.strip() if file_result.stdout else None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    if verbose and arch:
        print(f"  Architecture: {arch}")

    return BuildResult(
        success=True,
        so_path=so_path,
        build_dir=build_dir,
        cmake_output=cmake_result.stdout + cmake_result.stderr,
        build_output=build_output,
        arch=arch,
        tool_versions=tool_versions,
    )