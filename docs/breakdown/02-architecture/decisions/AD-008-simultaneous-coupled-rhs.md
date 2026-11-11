# AD-008: Simultaneous Coupled RHS for Internal Connections

## Status

Accepted

## Layer

Architecture

## Context

The wrapper instantiates all internal Model Exchange FMUs, concatenates their
continuous states into one `N_Vector`, and advances them with one
SUNDIALS ARKODE/CVODE integrator (`solver.py`, `combined_rhs`). That gives the
outer master one Co-Simulation boundary and one solver.

The original `combined_rhs` implementation only performed `setTime` /
`setContinuousStates` / `getDerivatives` per internal FMU. Internal connections
were propagated with `getReal`/`setReal` **outside** the RHS — once per internal
sub-step for fixed-step solvers, or once per communication step for adaptive
solvers — and then held constant while the states integrated. Algebraic loops
were resolved by one fixed-point pass before the integration loop began.

The consequence is a zero-order hold on the internal coupling. The lag is
`O(stepSize)` for fixed-step solvers and equal to the communication step for
adaptive solvers, and it does not shrink when the integration tolerance is
tightened. For a tightly coupled subsystem this is exactly the numerical
behaviour that grouping behind one boundary is meant to remove: the coupling
lag is moved inside the wrapper rather than eliminated. It also breaks the
assumption that a grouped realization reduces to a monolithic reference to
solver tolerance.

## Decision

Evaluate the internal coupling **inside `combined_rhs`**, at every integrator
stage. The generated RHS runs three passes:

1. load time and the owned slice of the combined state vector into every
   internal FMU (`fmi2SetTime`, `fmi2SetContinuousStates`);
2. resolve internal coupling at that exact `(t, y)` — propagate all
   connections and iterate algebraic loops to convergence;
3. read derivatives for every internal FMU (`fmi2GetDerivatives`).

Coupling is provided by two generated functions in `fixed_point_iteration.c`:

- `wrapper_propagate_connections` — one source-to-target sweep over all
  connections;
- `wrapper_resolve_coupling` — fixed-point iteration over the connection graph
  to the configured `AlgebraicLoop` tolerance / `max_iterations`, logging
  non-convergence at most once per instance.

`fmi2DoStep` is reduced to boundary handling: push inputs, integrate the
coupled system over the communication step, re-resolve coupling at the final
state, then read outputs.

## Alternatives Considered

- **Keep sampled coupling (status quo).** Simplest, but leaves an `O(step)`
  coupling lag that tolerance cannot remove; rejected because it defeats the
  numerical purpose of grouping.
- **Topologically order a single propagation pass.** Correct for acyclic
  graphs but not for cycles; the fixed-point iteration over all connections
  converges for acyclic graphs in one or two sweeps anyway, so ordering adds
  codegen complexity without removing the loop solve.
- **Newton solve for loops inside the RHS.** More robust for stiff loops but
  needs Jacobians the internal ME FMUs may not expose; deferred (see AD-003
  review trigger).
- **Hold loops once per communication step (status quo).** Moves the lag to the
  communication step; rejected for the same reason as sampled coupling.

## Consequences

- **Positive:** For connections without direct feed-through, the grouped
  trajectory converges to the monolithic reference as the integration
  tolerance is tightened. Coupling lag is no longer bounded by the step size.
- **Positive:** Adaptive solvers can keep a large communication step while
  controlling coupled accuracy through `solver.tolerance`.
- **Positive:** The architecture claim (one boundary) and the numerical claim
  (one coupled equation system) are now both true, and the two are no longer
  conflated.
- **Negative:** Coupling work is repeated on every RHS evaluation, so the
  wrapper is more expensive per step than sampled coupling, especially for
  implicit solvers and non-contractive loops.
- **Negative:** Non-convergent algebraic loops still have no guaranteed
  solution; the limitation in AD-003 is unchanged and now applies per RHS
  evaluation.

## Affected Artifacts

- `src/cs_fmu_packager/codegen/solver.py` — `combined_rhs` three-pass structure
- `src/cs_fmu_packager/codegen/fixed_point.py` — `wrapper_propagate_connections`,
  `wrapper_resolve_coupling`
- `src/cs_fmu_packager/codegen/fmi_interface.py` — `fmi2DoStep` boundary-only
- `src/cs_fmu_packager/codegen/fmi2_interface.h` — `coupling_warned` field
- `docs/COUPLING_SEMANTICS.md` — user-facing design and rationale
- `docs/CONFIGURATION.md` — solver semantics
- `03-implementation/modules/codegen-solver.md`,
  `03-implementation/modules/codegen-fixed-point.md`,
  `03-implementation/modules/codegen-fmi-interface.md`

## Verification

- `tests/test_codegen.py` asserts the RHS calls `wrapper_resolve_coupling`
  between state loading and derivative readback, and that `fmi2DoStep` calls
  `wrapper_resolve_coupling` / `wrapper_propagate_connections`.
- `tests/test_end_to_end.py::test_algebraic_loop_resolves_at_runtime` verifies
  the fixed point is reached at runtime.
- `tests/test_end_to_end.py::test_three_node_chain_two_stateful_fmus` verifies
  the combined state vector integrates correctly across coupled stateful FMUs.
- `tests/test_end_to_end.py::test_packager_matches_omc_reference` verifies the
  packaged trajectory against an OpenModelica Co-Simulation reference.

## Review Trigger

- When a use case needs guaranteed convergence for stiff or highly nonlinear
  loops (revisit a Newton/DAE formulation).
- When per-RHS coupling cost becomes a practical bottleneck.

## Supersedes

- None

## Superseded By

- None
