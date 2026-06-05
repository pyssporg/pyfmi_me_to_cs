# Co-Simulation FMU Packager

## Initial Description

The Co-Simulation FMU Packager is a tool for wrapping one or more FMI Model Exchange FMUs together with a local solver into a single FMI Co-Simulation FMU.

The packaged FMU exposes a normal Co-Simulation interface to an external master algorithm, while internally it instantiates Model Exchange FMUs, connects their variables, advances them with a selected solver, and exposes selected inputs, outputs, parameters, and status information at the wrapper boundary.

The main purpose is to make solver placement an explicit architectural choice. A coupled subsystem can be treated as one Co-Simulation component by the outer orchestration layer while retaining a structured internal Model Exchange representation and a local integration or loop-handling policy.

## Problem Statement

FMI-based simulation architectures often need to decide whether tight coupling should be exposed to the master algorithm or hidden inside a solver boundary. Exposing every component as a separate Co-Simulation FMU gives the master maximum visibility, but can introduce communication-step delay, algebraic-loop handling problems, and scheduler complexity. Grouping components manually into a custom Co-Simulation FMU can solve those issues, but usually requires ad hoc wrapper code.

This project provides a reusable packaging mechanism for that grouping step.

## Scope

In scope:

- Package multiple FMI Model Exchange FMUs into one FMI Co-Simulation FMU.
- Define internal connections between packaged Model Exchange FMUs.
- Define wrapper-level inputs, outputs, parameters, and exposed internal variables.
- Advance the internal system using a configurable local solver.
- Support fixed-step execution first.
- Support deterministic generated artifacts suitable for reproducible experiments.
- Report enough metadata to explain the wrapper boundary and solver assumptions.

Out of scope for the initial version:

- General-purpose FMI master replacement.
- Full graphical modeling environment.
- Automatic physical-model decomposition.
- Vendor-specific FMU extensions as required dependencies.
- Guaranteed convergence for arbitrary algebraic loops.
- Distributed or real-time execution.

## Intended Users

- Simulation architects who want to move a tightly coupled subsystem behind one Co-Simulation boundary.
- Experiment developers who need reproducible variants of the same logical system with different solver boundaries.
- FMI tool developers who need a reference wrapper pattern for ME-to-CS packaging.
- Researchers comparing decomposition, scheduling, and solver-placement effects.

## Design Intent

The packager should make the following distinction explicit:

- Model Exchange FMUs define equations and state derivatives.
- The wrapper defines local execution semantics.
- The outer Co-Simulation master sees one component boundary.

This separation is important because the numerical behavior of a packaged subsystem is not only a property of the internal FMUs. It also depends on the wrapper's solver, communication-step policy, event handling, and loop-handling behavior.

## Initial Project Outputs

- A command-line packaging tool.
- A declarative package specification format.
- Generated Co-Simulation FMUs.
- Generated wrapper metadata.
- Validation tests using small Model Exchange FMU examples.
- Documentation of supported solver and loop-handling policies.

## Relationship To Synthetic Propagation Study

The first motivating use case is strongly connected component grouping in a synthetic propagation benchmark. Each non-trivial strongly connected component can be packaged as one Co-Simulation FMU. The outer simulation sees the SCC as one FMU, while internal feedback is handled by the wrapper's local solver or explicit loop policy.

This use case should remain a driver, but the packager should be generic enough to support other coupled Model Exchange subsystems.
