# Requirements

## Functional Requirements

- FR-001: The tool shall package one or more FMI Model Exchange FMUs into one FMI Co-Simulation FMU.
- FR-002: The tool shall accept a declarative package specification describing internal FMUs, internal connections, exposed variables, solver settings, and wrapper metadata.
- FR-003: The generated Co-Simulation FMU shall expose configured wrapper inputs.
- FR-004: The generated Co-Simulation FMU shall expose configured wrapper outputs.
- FR-005: The generated Co-Simulation FMU shall expose configured parameters when supported by the wrapped variables or wrapper solver.
- FR-006: The generated Co-Simulation FMU shall instantiate all internal Model Exchange FMUs during wrapper initialization.
- FR-007: The wrapper shall map wrapper input values to configured internal FMU variables before internal advancement.
- FR-008: The wrapper shall map configured internal FMU variables to wrapper outputs after internal advancement.
- FR-009: The wrapper shall support fixed communication-step execution in the initial version.
- FR-010: The wrapper shall support at least one deterministic local solver in the initial version.
- FR-011: The wrapper shall record the local solver policy in generated metadata.
- FR-012: The wrapper shall report unsupported Model Exchange FMU features explicitly rather than silently ignoring them.
- FR-013: The tool shall generate a valid FMI model description for the packaged Co-Simulation FMU.
- FR-014: The tool shall preserve units, causality, variability, and descriptions for exposed variables when that metadata is available and unambiguous.
- FR-015: The tool shall detect missing internal variables referenced by the package specification.
- FR-016: The tool shall detect incompatible connection directions in the package specification.
- FR-017: The tool shall detect duplicate wrapper variable names before generating an FMU.
- FR-018: The tool shall support deterministic artifact naming.
- FR-019: The tool shall provide a command-line interface for packaging from a specification file.
- FR-020: The tool shall emit a machine-readable build report describing inputs, outputs, tool versions, solver policy, and warnings.

## Solver Requirements

- SR-001: The initial solver set shall include a fixed-step explicit solver suitable for simple continuous-state Model Exchange FMUs.
- SR-002: The solver interface shall be designed so additional solvers can be added without changing package specifications unrelated to solver configuration.
- SR-003: The wrapper shall distinguish the outer communication step from any internal solver step.
- SR-004: The wrapper shall allow the internal solver step size to be equal to or smaller than the outer communication step.
- SR-005: The wrapper shall define and document its behavior for algebraic or direct-feedthrough loops.
- SR-006: If fixed-point iteration is supported, the wrapper shall expose maximum iteration count, tolerance, and convergence status.
- SR-007: If delayed-feedback loop handling is supported, the wrapper shall document the delay semantics and initialization values.
- SR-008: Solver failure shall be reported through FMI status codes and diagnostic log messages.

## Initialization Requirements

- IR-001: The wrapper shall initialize internal FMUs in a deterministic order.
- IR-002: The wrapper shall apply configured start values before completing initialization.
- IR-003: The wrapper shall validate required wrapper parameters before entering simulation mode.
- IR-004: The wrapper shall document how initial values for internal loop states are chosen.
- IR-005: Initialization failures from internal FMUs shall be propagated to the wrapper user.

## Specification Requirements

- SPR-001: The package specification shall identify all internal FMU files.
- SPR-002: The package specification shall identify the FMI version and expected FMU kind for each internal FMU.
- SPR-003: The package specification shall define internal connections using stable variable references or variable names.
- SPR-004: The package specification shall define wrapper boundary variables explicitly.
- SPR-005: The package specification shall define solver policy explicitly.
- SPR-006: The package specification shall support optional human-readable rationale for the chosen wrapper boundary.
- SPR-007: The package specification shall be serializable as a text format suitable for version control.

## Non-Functional Requirements

- NFR-001: Generated artifacts shall be reproducible from the same input specification and tool version.
- NFR-002: Error messages shall identify the failing package specification element.
- NFR-003: The tool shall avoid hidden network access during packaging.
- NFR-004: The generated FMU shall not depend on absolute source paths at runtime.
- NFR-005: The generated FMU shall keep runtime dependencies explicit.
- NFR-006: The implementation shall be testable without proprietary FMI tools.
- NFR-007: The project shall include small reference FMUs or generated test FMUs for automated tests.
- NFR-008: The initial implementation shall prioritize correctness and traceability over runtime performance.
- NFR-009: The wrapper architecture shall allow later optimization of variable lookup and solver execution.

## Compatibility Requirements

- CR-001: The initial target shall be FMI 2.0 Co-Simulation output.
- CR-002: The initial input FMU target shall be FMI 2.0 Model Exchange.
- CR-003: The design should not prevent later FMI 3.0 support.
- CR-004: The generated FMU should be consumable by common FMI importers that support FMI 2.0 Co-Simulation.
- CR-005: Platform support shall be stated explicitly for each generated FMU.

## Validation Requirements

- VR-001: The project shall include a test that packages one scalar Model Exchange FMU into one Co-Simulation FMU.
- VR-002: The project shall include a test that packages two connected Model Exchange FMUs into one Co-Simulation FMU.
- VR-003: The project shall include a test that exposes wrapper inputs and outputs with stable names.
- VR-004: The project shall include a test for invalid variable references in the package specification.
- VR-005: The project shall include a test for duplicate wrapper variable names.
- VR-006: The project shall include a test for solver failure reporting.
- VR-007: The project shall include a test that verifies generated metadata contains solver policy and internal FMU mapping.
- VR-008: The project shall include a regression test for a strongly connected component packaging case.

## Initial Constraints

- C-001: The first version may support fixed-step execution only.
- C-002: The first version may reject internal FMUs that require unsupported event handling.
- C-003: The first version may reject variable-step solver requirements.
- C-004: The first version may support a limited set of scalar Real variables before arrays, integers, booleans, and strings are generalized.
- C-005: The first version may treat advanced FMI features such as clocks, binary variables, and scheduled execution as out of scope.

## Open Decisions

- OD-001: Decide whether the implementation generates C/C++ wrapper source, uses an existing FMI library runtime, or both.
- OD-002: Decide the first supported local solver.
- OD-003: Decide whether algebraic loops are handled by fixed-point iteration, delayed feedback, rejection, or configurable policies.
- OD-004: Decide whether internal Model Exchange FMUs are embedded inside the generated FMU resources or referenced externally.
- OD-005: Decide the package specification format, such as JSON, YAML, TOML, or SSP-derived input.
- OD-006: Decide the minimum supported operating systems and binary platforms.
