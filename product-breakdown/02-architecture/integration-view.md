# Integration View

## External Integrations

| Integration | Technology | Purpose | Phase |
| --- | --- | --- | --- |
| FMI 2.0 Model Exchange | Input FMU ZIP archives with `modelDescription.xml` | Read internal FMU variable metadata and load their shared libraries | Phase 2 |
| FMI 2.0 Co-Simulation | Generated `modelDescription.xml` + `.so` | Produce FMU consumable by any FMI 2.0 CS master algorithm | Phase 4, 6 |
| SUNDIALS ARKODE | C library via vcpkg | Provide ARKStep fixed-step ODE integrator | Phase 4, 5 |
| vcpkg | Package manager | Manage SUNDIALS dependency; provide CMake toolchain file | Phase 5 |
| CMake | Build system | Configure and compile generated C wrapper source | Phase 5 |
| GCC/Clang | C compiler | Compile generated C code to native `.so` shared library | Phase 5 |
| dlopen/dlsym | POSIX dynamic loading | Load internal FMU shared libraries at wrapper runtime | Runtime (generated C) |

## Protocol Details

### FMI 2.0 Co-Simulation Interface
- The generated FMU implements `fmi2Instantiate`, `fmi2FreeInstance`, `fmi2SetReal`/`fmi2GetReal`, `fmi2DoStep`, `fmi2SetupExperiment`, `fmi2EnterInitializationMode`, `fmi2ExitInitializationMode`, `fmi2Terminate`, and status inquiry functions.
- All FMI 2.0 CS standard functions are exported from the `.so` as `FMI2_Export` symbols.

### SUNDIALS ARKODE
- Used in fixed-step explicit mode via `ARKStepCreate` (with `NULL` for implicit component) and `ARKStepSetFixedStep`.
- The combined RHS function calls each internal FMU's `getDerivatives` and concatenates the results into the ARKODE state vector.

## Relevant Decisions

- AD-001: C Wrapper Architecture (native `.so`, no Python runtime)
- AD-002: SUNDIALS Solver (via vcpkg)
- AD-006: Linux x86_64 Only (v1)