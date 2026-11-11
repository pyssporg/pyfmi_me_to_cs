# Module: codegen/fixed_point

**File:** `src/cs_fmu_packager/codegen/fixed_point.py`

## Responsibility

Generates `fixed_point_iteration.c` — the internal coupling evaluation used by `combined_rhs`: a single propagation pass plus fixed-point iteration that resolves algebraic loops (strongly connected components) in the internal FMU graph at a fixed state and time.

## Key Functions

| Function | Description |
| --- | --- |
| `generate_fixed_point_impl(spec, mapping)` | Generate fixed_point_iteration.c content |

## Generated C Functions

| Function | Description |
| --- | --- |
| `wrapper_propagate_connections()` | Single source-to-target sweep over all internal connections at the current state; resolves the acyclic part of the graph and refreshes feed-through outputs |
| `fixed_point_solve_loop()` | Fixed-point iteration over a connection list — gets source values, sets target values, checks convergence against tolerance |
| `wrapper_resolve_coupling()` | Resolve the full connection graph at the current state/time; returns 0 on success, -1 on allocation failure; logs non-convergence at most once per instance |

## Convergence Behavior

- Iterates up to `max_iterations` times
- Convergence: max difference across all connections < tolerance
- Non-convergence: logged once as `fmi2Warning` via the FMI logger callback
- Allocation failure: returns -1 (error)

Called from `combined_rhs` on every integrator stage (AD-008); see
`docs/COUPLING_SEMANTICS.md`.

## Source

- `src/cs_fmu_packager/codegen/fixed_point.py` (149 lines)