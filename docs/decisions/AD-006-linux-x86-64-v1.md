# AD-006: Linux x86_64 Only (v1)

**Status:** Accepted

## Context

The generated FMU must include a compiled shared library for the target platform. Supporting multiple platforms multiplies the build matrix and testing effort. For v1, we must choose a single target to minimize initial complexity.

Linux x86_64 is the most common platform for simulation workloads in research and server environments. It is also the platform where vcpkg and SUNDIALS are easiest to set up and test.

## Decision

Support **Linux x86_64 only** for v1. Cross-platform support (macOS ARM, Windows x86_64) is planned for future versions. The architecture is designed to accommodate additional platforms by extending the `binaries/<platform>/` directory structure defined by the FMI standard.

## Consequences

- **Positive:** Simplified build and testing for initial development.
- **Positive:** vcpkg, SUNDIALS, and GCC are natively available on Linux.
- **Negative:** Windows and macOS users cannot generate FMUs in v1.
- **Negative:** Generated FMUs cannot be consumed on non-Linux platforms.
- **Negative:** Platform detection and multi-target builds must be added later.

## Affected Artifacts

- `src/cs_fmu_packager/builder.py` — Linux-specific CMake configuration
- `src/cs_fmu_packager/packager.py` — Fixed `binaries/linux64/` target path
- `CMakePresets.json` — Linux build preset