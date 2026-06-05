# AD-003: Fixed-Point Iteration for Algebraic Loops

**Status:** Accepted

## Context

When internal FMUs are connected with feedback (direct feed-through from output back to input), an algebraic loop exists. The wrapper must handle these loops. Three approaches were considered:

1. **Delayed feedback:** Use values from the previous communication step — simplest but introduces one-step delay.
2. **Fixed-point iteration:** Iterate within each communication step until convergence — standard approach when convergence is expected.
3. **Rejection:** Raise an error and refuse to handle algebraic loops — safest but reduces applicability.

The primary use case (UC-001: Strongly Connected Components) requires handling algebraic loops. Fixed-point iteration is standard in co-simulation wrappers and matches what most FMI masters use.

## Decision

Use **fixed-point iteration** for algebraic loop handling. Expose `max_iterations` and `tolerance` as configurable parameters in the package specification. Report convergence status through FMI status codes and diagnostic logs.

## Consequences

- **Positive:** Stateless, easy to implement, and matches co-simulation practice.
- **Positive:** Convergence criteria are user-configurable.
- **Negative:** No guaranteed convergence for stiff or highly nonlinear loops.
- **Negative:** Fixed-point iteration may require many iterations for tight tolerances.
- **Negative:** Extra computational cost per communication step when loops exist.

## Affected Artifacts

- `src/cs_fmu_packager/models.py` — `AlgebraicLoopConfig` dataclass
- `src/cs_fmu_packager/codegen/fixed_point.py` — C code generation for iteration loops
- `src/cs_fmu_packager/mapper.py` — SCC detection via Tarjan's algorithm