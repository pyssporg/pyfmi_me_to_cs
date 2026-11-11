# AD-002: SUNDIALS Solver

## Status

Accepted

## Layer

Architecture

## Context

The generated Co-Simulation FMU needs a local ODE solver to advance the internal Model Exchange FMUs between communication steps. Several options exist: SUNDIALS (ARKODE/CVODE), a custom fixed-step Euler implementation, or external solver libraries like GSL.

SUNDIALS is a well-established, open-source numerical solver library developed by Lawrence Livermore National Laboratory. It provides ARKODE for both explicit and implicit fixed-step integration, which matches the v1 requirement for fixed-step execution. SUNDIALS is available via vcpkg, which is already the chosen dependency manager.

A custom Euler implementation would be simpler but would limit future extensibility to variable-step, stiff, or implicit solvers. Using SUNDIALS provides a clear extension path.

## Decision

Use **SUNDIALS** (via vcpkg) as the solver basis. Start with ARKODE in fixed-step explicit mode (forward Euler or Runge-Kutta), with solver type made configurable via the package specification.

## Alternatives Considered

- Custom fixed-step Euler — simpler to implement but limits future extensibility to more advanced solvers.
- GSL — less focused on ODE/DAE integration; SUNDIALS is more specialized for this use case.
- No local solver, delegate to external master — contradicts the design intent of solver placement.

## Consequences

- **Positive:** SUNDIALS provides production-quality, well-tested numerical integration.
- **Positive:** ARKODE supports fixed-step mode suitable for v1.
- **Positive:** Extensible to implicit solvers, adaptive stepping, and stiff systems in future versions.
- **Negative:** Adds a build dependency on SUNDIALS via vcpkg.
- **Negative:** vcpkg installation and SUNDIALS compilation increase initial setup time.
- **Negative:** Generated FMU links SUNDIALS libraries, increasing binary size.

## Affected Artifacts

- `03-implementation/modules/codegen-solver.md` — ARKODE integration code generation
- `03-implementation/configuration.md` — vcpkg.json dependency declaration
- `02-architecture/integration-view.md` — SUNDIALS ARKODE integration
- `03-implementation/modules/builder.md` — CMake FindSUNDIALS integration

## Verification

- `solver_init()` and `solver_step()` return 0 for a test FMU with known continuous states.
- ARKStep memory is allocated and freed correctly without leaks.

## Review Trigger

- When implicit solvers or adaptive stepping are needed for a use case.
- If SUNDIALS becomes unmaintained or incompatible with future FMI standards.