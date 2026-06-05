# AD-007: vcpkg Package Manager

## Status

Accepted

## Layer

Architecture

## Context

The generated Co-Simulation FMU requires compiled native C code, which in turn requires native C dependencies. Currently, the project depends on SUNDIALS (ARKODE) for ODE integration (see AD-002), and future versions may introduce additional native dependencies (e.g., for alternative solvers, linear algebra, or platform support).

The project has been using vcpkg implicitly since its inception — AD-002 references it, `vcpkg.json` declares the SUNDIALS dependency, the builder discovers `VCPKG_ROOT` at runtime, build configuration depends on the vcpkg CMake toolchain file, and the environments specification lists vcpkg with `VCPKG_ROOT` as a build requirement. However, the choice of vcpkg as the project's package manager has never been formally documented.

Several alternatives exist for managing native C/C++ dependencies: Conan, system package managers (apt, yum), git submodules, or manual dependency tracking. Without a formal decision, the project risks inconsistent dependency management approaches across contributors, unclear onboarding expectations, and ad-hoc workarounds when vcpkg is unavailable.

This decision formalizes vcpkg as the project's designated package manager and establishes that vcpkg is a required build dependency — not optional and not a convenience tool.

## Decision

Use **vcpkg** as the project's native package manager for all C/C++ dependencies. vcpkg is a **required build dependency** — developers and CI systems must have vcpkg installed with `VCPKG_ROOT` set (or vcpkg discoverable through an equivalent mechanism) before building the project.

All native dependencies are declared in `vcpkg.json` at the repository root. The `vcpkg.cmake` toolchain file is used by CMake for dependency resolution. Dependency versions are pinned via the vcpkg baseline mechanism for reproducible builds.

## Alternatives Considered

- **Conan** — More flexible but adds another package-manager concept to the project; steeper learning curve; less commonly used in the FMI/numerical-simulation community on Linux.
- **System package managers (apt, yum, brew)** — Not portable across distributions; no version pinning for reproducibility; package availability and versions vary by distribution.
- **Git submodules** — Manual dependency tracking without version resolution; no dependency graph or transitive dependency management.
- **No package manager / manual dependency handling** — Fragile; requires developers to manually locate, build, and link dependencies; no reproducibility guarantee.

## Consequences

- **Positive:** Single, consistent mechanism for all native dependencies — developers learn one tool.
- **Positive:** Reproducible dependency resolution via vcpkg baseline (pinned dependency versions).
- **Positive:** Broad platform support (Linux, macOS, Windows) for future cross-platform expansion.
- **Positive:** CMake integration via `CMAKE_TOOLCHAIN_FILE` is well-documented and widely used.
- **Positive:** The `VCPKG_ROOT` environment variable is a well-known convention for locating vcpkg.
- **Negative:** Adds an onboarding step — new contributors must install vcpkg before building.
- **Negative:** vcpkg builds dependencies from source, increasing first-build time.
- **Negative:** Projects without vcpkg installed cannot build the generated C wrapper; `VCPKG_ROOT` being unset produces a clear error.
- **Negative:** Binary caching and overlay ports require additional setup for advanced vcpkg usage.

## Affected Artifacts

- `vcpkg.json` — Manifest file declaring all native dependencies
- `03-implementation/environments.md` — Build environment table lists vcpkg requirement with `VCPKG_ROOT`
- `03-implementation/configuration.md` — Documents vcpkg.json manifest and CMakePresets.json toolchain integration
- `03-implementation/modules/builder.md` — Runtime vcpkg root discovery logic
- `03-implementation/modules/cli.md` — `--vcpkg-root` CLI option
- `02-architecture/integration-view.md` — Lists vcpkg as an external integration
- `02-architecture/context-view.md` — Lists Build Tools (including vcpkg) as external actors
- `02-architecture/decisions/AD-002-sundials-solver.md` — Already references vcpkg as the dependency mechanism; AD-007 formalizes that reference
- `02-architecture/decisions/AD-006-linux-x86-64-v1.md` — References vcpkg availability on Linux as a positive factor; AD-007 formalizes the dependency

## Verification

- Repository root contains a valid `vcpkg.json` with declared dependencies.
- Build fails with a clear error message if `VCPKG_ROOT` is unset or vcpkg is not found.
- CMake configuration succeeds when `CMAKE_TOOLCHAIN_FILE` points to a valid vcpkg toolchain.
- All native dependencies used in the project are declared in `vcpkg.json` (no manual library detection fallbacks).
- CI pipeline installs vcpkg and sets `VCPKG_ROOT` before build.

## Review Trigger

- If vcpkg becomes unmaintained or introduces breaking changes that affect the project.
- If the project adds a native dependency that vcpkg does not provide or cannot easily build.
- If a contributor demonstrates that an alternative package manager provides material improvement in build time, reproducibility, or cross-platform support.
- When considering non-Linux platform support (macOS ARM, Windows x86_64), review whether vcpkg sufficiently supports those targets.