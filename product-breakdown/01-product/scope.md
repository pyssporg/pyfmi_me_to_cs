# Scope

## In Scope (v1)

1. Package multiple FMI Model Exchange FMUs into one FMI Co-Simulation FMU.
2. Define internal connections between packaged Model Exchange FMUs.
3. Define wrapper-level inputs, outputs, parameters, and exposed internal variables.
4. Advance the internal system using a configurable local solver.
5. Support fixed-step execution first.
6. Support deterministic generated artifacts suitable for reproducible experiments.
7. Report enough metadata to explain the wrapper boundary and solver assumptions.

## Out of Scope (v1)

1. General-purpose FMI master replacement.
2. Full graphical modeling environment.
3. Automatic physical-model decomposition.
4. Vendor-specific FMU extensions as required dependencies.
5. Guaranteed convergence for arbitrary algebraic loops.
6. Distributed or real-time execution.

## Source

Derived from `cs-fmu-packager-project/README.md` (Scope section).