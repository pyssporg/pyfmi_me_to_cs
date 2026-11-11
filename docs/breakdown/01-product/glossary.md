# Glossary

| Term | Definition |
| --- | --- |
| Co-Simulation FMU | An FMU that implements the FMI 2.0 Co-Simulation interface, where the master algorithm provides inputs and collects outputs at discrete communication points. |
| Communication Step | The time interval between successive calls to `fmi2DoStep` by the external master algorithm. |
| Connection | A directed variable-level link between two internal FMUs, connecting a source FMU output to a target FMU input. |
| Deterministic Artifact | A generated file that is byte-identical across repeated runs with the same inputs (excluding intentionally varying timestamps). |
| dlopen | The POSIX dynamic library loading function used to load internal FMU shared libraries at runtime. |
| Fixed-Point Iteration | An iterative method for resolving algebraic loops within a single communication step by repeatedly evaluating connections until convergence. |
| Fixed-Step Solver | An ODE solver that advances state using a constant internal step size. |
| FMU | Functional Mock-up Unit — a ZIP archive containing an FMI-compliant model description and compiled binaries. |
| Internal FMU | An input Model Exchange FMU that is embedded inside the generated Co-Simulation FMU and instantiated by the wrapper at runtime. |
| Mapping | The resolved association between wrapper boundary variables and internal FMU variables, including value references and type information. |
| Model Exchange FMU | An FMU that implements the FMI 2.0 Model Exchange interface, exposing equations and state derivatives to the calling environment. |
| Package Specification | A complete SSP package (`.ssp`) — `SystemStructure.ssd` plus embedded FMUs — that declares the FMU inputs, connections, boundary variables, and solver configuration for a packaging operation. |
| SCC | Strongly Connected Component — a set of FMUs that form an algebraic loop through their interconnections, detected via Tarjan's algorithm. |
| Solver Placement | The architectural choice of which FMUs are grouped behind a single solver boundary inside a Co-Simulation FMU. |
| Value Reference | An integer identifier used in the FMI 2.0 protocol to refer to a specific ScalarVariable within an FMU. |
| Wrapper | The generated C code that instantiates internal FMUs, manages their lifecycle, maps variables, and drives the local solver. |
| Build Report | A JSON file emitted after a packaging run, summarizing tool versions, FMU count, solver policy, and warnings. |