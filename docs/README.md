# Documentation

User-facing documentation for cs-fmu-packager. The project also keeps a full
product breakdown (intent, product, architecture, implementation,
verification, operation, evolution) under [`product-breakdown/`](../product-breakdown/README.md).

- [Configuration reference](CONFIGURATION.md) — the canonical reference for
  every configurable aspect: vendor annotation schema, solver types, runtime
  solver parameters, boundary variables, precedence, and defaults.
- [Coupling and solver semantics](COUPLING_SEMANTICS.md) — what the packaged
  FMU solves: one boundary, one coupled equation system, how internal
  connections and algebraic loops are evaluated, and the practical
  consequences for solver settings.
- [Getting started](../GETTING_STARTED.md) — step-by-step walkthrough to your
  first Co-Simulation FMU build.
- [Runnable example](../examples/quickstart/README.md) — an executable
  integrator → gain example with full build and simulation instructions.
- [README](../README.md) — project overview, CLI reference, prerequisites.