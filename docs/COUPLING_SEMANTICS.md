# Coupling and solver semantics

This document explains what the packaged Co-Simulation FMU actually solves, how
the internal Model Exchange FMUs are coupled, and why the generated wrapper is
structured the way it is. It is the reference for interpreting results and for
choosing solver settings.

## The one-sentence model

The packaged FMU is **one Co-Simulation boundary around one coupled equation
system**: all internal ME FMUs contribute their continuous states to a single
state vector, internal connections are evaluated at every integrator stage, and
one SUNDIALS integrator advances the whole system.

## What the master sees

An external master sees a single FMI 2.0 Co-Simulation FMU:

- one `fmi2Instantiate` / `fmi2DoStep` cycle,
- one set of boundary inputs, outputs, and parameters,
- one reserved `solver.*` parameter group.

It does not see the internal ME FMUs, their connections, or the local solver.

## What happens inside one `fmi2DoStep`

`fmi2DoStep(currentCommunicationPoint, communicationStepSize, ...)` runs four
steps (generated `fmi2_interface.c`):

1. **Push boundary inputs.** The master's inputs are written to the internal
   FMUs and held constant for the whole communication step, per FMI
   Co-Simulation semantics.
2. **Integrate the coupled system.** The communication step is sliced into
   fixed steps (`fixed_step`, `fixed_rk2`, `fixed_rk4`, `backward_euler`) or
   evolved adaptively to the communication point (`variable_step`, `cvode`).
   Each `solver_step` call hands the combined state vector to ARKODE/CVODE.
3. **Re-establish coupling at the final state.** The connection graph is
   resolved once more at the end-of-step state so that feed-through outputs are
   current.
4. **Update boundary outputs.** Wrapper outputs are read from the internal
   FMUs.

## The combined RHS: how coupling is evaluated

The core of the design is `combined_rhs()` in `solver_integration.c`. On every
integrator stage (including the internal stages of a Runge-Kutta step and the
difference-quotient Jacobian perturbations of implicit methods) it runs three
passes:

1. **Load state.** For every internal FMU: `fmi2SetTime(t)` and
   `fmi2SetContinuousStates(y_slice)`.
2. **Resolve coupling.** Internal connections are propagated from source
   outputs to target inputs, and algebraic loops are iterated to convergence —
   **at this exact `t` and `y`**.
3. **Read derivatives.** For every internal FMU: `fmi2GetDerivatives(ydot_slice)`.

Because coupling is resolved inside the RHS, the integrator's error control
applies to the coupled system as a whole. The internal coupling is not sampled
at a communication or fixed step and then held; it is part of the equation the
integrator solves.

### Algebraic loops

A connection cycle (a strongly connected component in the connection graph,
detected at packaging time and reported as "algebraic loops") cannot be
evaluated in a single propagation pass. These loops are resolved by
fixed-point iteration at the fixed `(t, y)` of the current RHS evaluation:

- iterate until the largest change across all connection values is below
  `algebraic_loop.tolerance`, or `algebraic_loop.max_iterations` is reached;
- non-convergence is reported once through the FMI logger as `fmi2Warning`;
- the iteration is configured in the package specification (see
  [Configuration](CONFIGURATION.md)).

This is a *simultaneous* treatment of the loop in the sense that the loop
residual is driven to the loop tolerance at every integrator stage. It is not a
Newton solve, so a non-contractive loop (loop gain at or above one) may not
converge — the same limitation documented in AD-003.

## Why this design

### The problem with sampled internal coupling

A simpler wrapper could propagate connections once per communication step (or
once per fixed sub-step) and then hold the target values while the states
integrate. That is a zero-order hold on the coupling: it introduces an
`O(step)` lag between coupled components, and — critically — the lag does not
shrink when the integration tolerance is tightened, because tolerance only
controls state integration, not when coupling is sampled.

For a tightly coupled subsystem that lag is exactly the numerical behaviour the
grouping was meant to remove. Moving the coupling into the RHS eliminates it:
for connections without direct feed-through the coupled trajectory now
converges to the monolithic solution as the integration tolerance is tightened.

### Architecture vs numerics

Two claims must be kept distinct:

- **Architecture:** grouping places one solver and one boundary around the
  subsystem. Always true for this tool.
- **Numerics:** grouping makes the internal system a single coupled equation
  system evaluated by that solver. True because of the RHS design described
  above.

The second claim does not follow from the first. It is the RHS structure that
delivers it.

## Practical consequences

| Choice | Effect |
| --- | --- |
| `fixed_step` / `fixed_rk2` / `fixed_rk4` | Coupling is evaluated at every stage; accuracy is controlled by `solver.step_size` and the method order. |
| `variable_step` / `cvode` | Coupling is evaluated at every adaptive stage; accuracy is controlled by `solver.tolerance`, independent of the communication step. |
| `backward_euler` | Implicit stages call the RHS (and thus the coupling solve) repeatedly for Jacobian and Newton iterations; expect more RHS evaluations. |
| `algebraic_loop.tolerance` | Controls how tightly internal cycles are resolved. Should be at or below `solver.tolerance`. |
| `algebraic_loop.max_iterations` | Caps the per-RHS loop effort. Raise it for stiff or strongly coupled loops. |

### Performance

Resolving coupling on every RHS evaluation is more expensive than holding it
once per step, because the work is repeated for every integrator stage. For
purely acyclic connection graphs the fixed-point iteration converges in one or
two sweeps, so the overhead is small. For algebraic loops the cost scales with
`max_iterations`; implicit solvers multiply it by the number of RHS evaluations
per step.

### When the master should tighten tolerance instead of shrinking the step

For `variable_step`/`cvode` the communication step no longer bounds coupling
accuracy. A master can keep a large communication step for scheduling reasons
and still obtain an accurate coupled trajectory by tightening
`solver.tolerance`. This is the main practical benefit of the grouping.

## Related documents

- [Configuration reference](CONFIGURATION.md) — solver types and runtime
  parameters.
- AD-003 — fixed-point iteration for algebraic loops.
- AD-008 — simultaneous coupled RHS design decision.
