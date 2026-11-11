# AD-006: Linux x86_64 Only (v1)

## Status

Accepted

## Layer

Architecture

## Context

The generated FMU must include a compiled shared library for the target platform. Supporting multiple platforms multiplies the build matrix and testing effort. For v1, we must choose a single target to minimize initial complexity.

Linux x86_64 is the most common platform for simulation workloads in research and server environments. It is also the platform where vcpkg and SUNDIALS are easiest to set up and test.

## Decision

Support **Linux x86_64 only** for v1. Cross-platform support (macOS ARM, Windows x86_64) is planned for future versions. The architecture is designed to accommodate additional platforms by extending the `binaries/<platform>/` directory structure defined by the FMI standard.

## Alternatives Considered

- Multi-platform from the start — more complex build matrix and testing overhead.
- Windows x86_64 first — less common for research simulation workloads.
- macOS ARM first — growing but still a minority in the simulation community.

## Consequences

- **Positive:** Simplified build and testing for initial development.
- **Positive:** vcpkg, SUNDIALS, and GCC are natively available on Linux.
- **Negative:** Windows and macOS users cannot generate FMUs in v1.
- **Negative:** Generated FMUs cannot be consumed on non-Linux platforms.
- **Negative:** Platform detection and multi-target builds must be added later.

## Affected Artifacts

- `03-implementation/modules/builder.md` — Linux-specific CMake configuration
- `02-architecture/deployment-view.md` — Fixed `binaries/linux64/` target path
- `03-implementation/configuration.md` — CMakePresets.json Linux build preset
- `03-implementation/environments.md` — Linux x86_64 as supported environment

## Verification

- Build succeeds on Linux x86_64 with CMake, GCC, vcpkg, and SUNDIALS.
- Generated `.so` file is an x86_64 ELF binary.
- Non-Linux platforms produce a clear error message during CMake configuration.

## Review Trigger

- When a user or use case requires Windows or macOS FMU generation.
- When the project has sufficient CI capacity for multi-platform builds.