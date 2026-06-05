# Module: codegen/fixed_point

**File:** `src/cs_fmu_packager/codegen/fixed_point.py`

## Responsibility

Generates `fixed_point_iteration.c` — the fixed-point iteration implementation for resolving algebraic loops (strongly connected components) in the internal FMU graph.

## Key Functions

| Function | Description |
| --- | --- |
| `generate_fixed_point_impl(spec, mapping)` | Generate fixed_point_iteration.c content |

## Generated C Functions

| Function | Description |
| --- | --- |
| `fixed_point_solve_loop()` | Perform fixed-point iteration for a single algebraic loop — gets source values, sets target values, checks convergence against tolerance |
| `fixed_point_resolve_all()` | Resolve all algebraic loops in the wrapper; returns 0 on success, -1 on allocation failure |

## Convergence Behavior

- Iterates up to `max_iterations` times
- Convergence: max difference across all connections < tolerance
- Non-convergence: logged as `fmi2Warning` via FMI logger callback
- Allocation failure: returns -1 (error)

## Source

- `src/cs_fmu_packager/codegen/fixed_point.py` (149 lines)