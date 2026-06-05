# Module: codegen/solver

**File:** `src/cs_fmu_packager/codegen/solver.py`

## Responsibility

Generates `solver_integration.c` — the SUNDIALS ARKODE fixed-step integrator implementation for the wrapper. Contains the combined RHS function that calls all internal FMU `getDerivatives` and concatenates the results.

## Key Functions

| Function | Description |
| --- | --- |
| `generate_solver_impl(spec, mapping)` | Generate solver_integration.c content |

## Generated C Functions

| Function | Description |
| --- | --- |
| `combined_rhs()` | Compute derivatives from all internal FMUs into a single ARKODE state vector |
| `solver_init()` | Initialize ARKStep memory, allocate state vector, set fixed step size |
| `solver_step()` | Perform one integration step using ARKStepEvolve |
| `solver_free()` | Free solver-allocated resources |

## Source

- `src/cs_fmu_packager/codegen/solver.py` (200 lines)