# Module: codegen/solver

**File:** `src/cs_fmu_packager/codegen/solver.py`

## Responsibility

Generates `solver_integration.c` — the SUNDIALS ARKODE/CVODE integrator implementation for the wrapper. Contains the combined RHS function that evaluates the internal FMUs as one coupled equation system: it loads the combined state, resolves internal coupling at the current `(t, y)`, then reads derivatives and concatenates them.

## Key Functions

| Function | Description |
| --- | --- |
| `generate_solver_impl(spec, mapping)` | Generate solver_integration.c content |

## Generated C Functions

| Function | Description |
| --- | --- |
| `combined_rhs()` | Three-pass coupled RHS: (1) `setTime`/`setContinuousStates` for all internal FMUs, (2) `wrapper_resolve_coupling()` to propagate connections and resolve algebraic loops at the current state, (3) `getDerivatives` for all internal FMUs |
| `solver_init()` | Initialize ARKStep memory, allocate state vector, set fixed step size |
| `solver_step()` | Perform one integration step using ARKStepEvolve |
| `solver_free()` | Free solver-allocated resources |

See AD-008 and `docs/COUPLING_SEMANTICS.md` for the rationale.

## Source

- `src/cs_fmu_packager/codegen/solver.py` (200 lines)