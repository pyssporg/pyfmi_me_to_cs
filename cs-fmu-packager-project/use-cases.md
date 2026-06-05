# Use Cases

## UC-001: Package A Strongly Connected Component

An experiment generator identifies a strongly connected component in a directed dependency graph. The generator provides the Model Exchange FMUs for the nodes in the component, their internal connections, and the variables that cross the component boundary.

The packager creates one Co-Simulation FMU representing the full SCC.

Primary value:

- The external master no longer needs to schedule the internal feedback loop directly.
- The SCC becomes a single solver boundary.
- The experiment can compare exposed-loop and grouped-loop architectures.

Success outcome:

- The generated Co-Simulation FMU can be connected in an SSP or equivalent system description as one component.

## UC-002: Wrap A Tightly Coupled Physical Subsystem

A simulation architect has several Model Exchange FMUs that interact strongly, such as controller-plant pairs, coupled thermal components, or multi-body subsystems. Running them as separate Co-Simulation FMUs produces poor stability or excessive communication sensitivity.

The architect packages the subsystem as one Co-Simulation FMU with a local solver.

Primary value:

- Local integration can use smaller internal steps than the outer communication step.
- Strong coupling can be handled inside the wrapper.
- The outer simulation remains modular.

Success outcome:

- The subsystem has a stable Co-Simulation interface with documented local solver assumptions.

## UC-003: Compare Solver Placement Alternatives

A researcher wants to compare numerical behavior across multiple decompositions of the same logical system.

The same Model Exchange FMUs are packaged into different Co-Simulation boundaries:

- all components exposed separately,
- selected strongly connected components grouped,
- the full system grouped into one FMU.

Primary value:

- The logical model can stay constant while the solver boundaries change.
- The resulting experiments isolate decomposition and solver-placement effects.

Success outcome:

- Generated FMUs and metadata make each packaging boundary traceable and reproducible.

## UC-004: Publish A Reusable Subsystem FMU

A model supplier wants to distribute a subsystem as one Co-Simulation FMU while preserving internal modular development based on Model Exchange FMUs.

The supplier packages the internal FMUs and exposes only the intended boundary variables.

Primary value:

- Internal model structure can be hidden or simplified for users.
- The delivered artifact is easier for downstream tools to consume.
- Internal solver settings can be controlled by the supplier.

Success outcome:

- Downstream users can instantiate the packaged FMU without knowing the internal FMU graph.

## UC-005: Validate Wrapper Semantics

A tool developer needs to verify that a generated wrapper handles initialization, stepping, events, and variable propagation correctly.

The developer packages small reference Model Exchange FMUs with known behavior and checks wrapper outputs against expected traces.

Primary value:

- Wrapper behavior can be tested independently from complex physical models.
- Solver and event-handling limitations can be documented early.

Success outcome:

- Automated tests catch regressions in stepping, variable mapping, and metadata generation.

## UC-006: Generate Co-Simulation FMUs From A Declarative Spec

An upstream generator produces a package specification from a graph, SysML model, SSP model, or other architecture description.

The packager consumes the specification and creates a Co-Simulation FMU without manual wrapper programming.

Primary value:

- Packaging becomes reproducible and automatable.
- Large experiment matrices can be generated consistently.
- Tool-specific wrapper code is minimized.

Success outcome:

- The same specification produces byte- or metadata-stable artifacts across runs, except for explicitly recorded build timestamps or tool versions.
