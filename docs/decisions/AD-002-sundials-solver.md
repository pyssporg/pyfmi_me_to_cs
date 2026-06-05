# AD-002: SUNDIALS Solver

**Status:** Accepted

## Context

The generated Co-Simulation FMU needs a local ODE solver to advance the internal Model Exchange FMUs between communication steps. Several options exist: SUNDIALS (ARKODE/CVODE), a custom fixed-step Euler implementation, or external solver libraries like GSL.

SUNDIALS is a well-established, open-source numerical solver library developed by Lawrence Livermore National Laboratory. It provides ARKODE for both explicit and implicit fixed-step integration, which matches our v1 requirement for fixed-step execution. SUNDIALS is available via vcpkg, which is already the chosen dependency manager.

A custom Euler implementation would be simpler but would limit future extensibility to variable-step, stiff, or implicit solvers. Using SUNDIALS provides a clear extension path.

## Decision

Use **SUNDIALS** (via vcpkg) as the solver basis. Start with ARKODE in fixed-step explicit mode (forward Euler or Runge-Kutta), with solver type made configurable via the package specification.

## Consequences

- **Positive:** SUNDIALS provides production-quality, well-tested numerical integration.
- **Positive:** ARKODE supports fixed-step mode suitable for v1.
- **Positive:** Extensible to implicit solvers, adaptive stepping, and stiff systems in future versions.
- **Negative:** Adds a build dependency on SUNDIALS via vcpkg.
- **Negative:** vcpkg installation and SUNDIALS compilation increase initial setup time.
- **Negative:** Generated FMU links SUNDIALS libraries, increasing binary size.

## Affected Artifacts

- `vcpkg.json` — sundials dependency declaration
- `src/cs_fmu_packager/codegen/solver.py` — ARKODE integration code generation
- `src/cs_fmu_packager/codegen/fmi_interface.py` — `fmi2DoStep` implementation
- `src/cs_fmu_packager/builder.py` — CMake FindSUNDIALS integration