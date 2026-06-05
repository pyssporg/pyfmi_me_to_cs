# Purpose

## Problem Statement

FMI-based simulation architectures often need to decide whether tight coupling should be exposed to the master algorithm or hidden inside a solver boundary. Exposing every component as a separate Co-Simulation FMU gives the master maximum visibility, but can introduce communication-step delay, algebraic-loop handling problems, and scheduler complexity. Grouping components manually into a custom Co-Simulation FMU can solve those issues, but usually requires ad hoc wrapper code.

This project provides a reusable packaging mechanism for that grouping step.

## Product Description

The Co-Simulation FMU Packager is a tool for wrapping one or more FMI Model Exchange FMUs together with a local solver into a single FMI Co-Simulation FMU.

The packaged FMU exposes a normal Co-Simulation interface to an external master algorithm, while internally it instantiates Model Exchange FMUs, connects their variables, advances them with a selected solver, and exposes selected inputs, outputs, parameters, and status information at the wrapper boundary.

The main purpose is to make solver placement an explicit architectural choice. A coupled subsystem can be treated as one Co-Simulation component by the outer orchestration layer while retaining a structured internal Model Exchange representation and a local integration or loop-handling policy.

