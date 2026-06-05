# Functional Requirements

| ID | Requirement | Source |
| --- | --- | --- |
| FR-001 | The tool shall package one or more FMI Model Exchange FMUs into one FMI Co-Simulation FMU. | `cs-fmu-packager-project/requirements.md` |
| FR-002 | The tool shall accept a declarative package specification describing internal FMUs, internal connections, exposed variables, solver settings, and wrapper metadata. | `cs-fmu-packager-project/requirements.md` |
| FR-003 | The generated Co-Simulation FMU shall expose configured wrapper inputs. | `cs-fmu-packager-project/requirements.md` |
| FR-004 | The generated Co-Simulation FMU shall expose configured wrapper outputs. | `cs-fmu-packager-project/requirements.md` |
| FR-005 | The generated Co-Simulation FMU shall expose configured parameters when supported by the wrapped variables or wrapper solver. | `cs-fmu-packager-project/requirements.md` |
| FR-006 | The generated Co-Simulation FMU shall instantiate all internal Model Exchange FMUs during wrapper initialization. | `cs-fmu-packager-project/requirements.md` |
| FR-007 | The wrapper shall map wrapper input values to configured internal FMU variables before internal advancement. | `cs-fmu-packager-project/requirements.md` |
| FR-008 | The wrapper shall map configured internal FMU variables to wrapper outputs after internal advancement. | `cs-fmu-packager-project/requirements.md` |
| FR-009 | The wrapper shall support fixed communication-step execution in the initial version. | `cs-fmu-packager-project/requirements.md` |
| FR-010 | The wrapper shall support at least one deterministic local solver in the initial version. | `cs-fmu-packager-project/requirements.md` |
| FR-011 | The wrapper shall record the local solver policy in generated metadata. | `cs-fmu-packager-project/requirements.md` |
| FR-012 | The wrapper shall report unsupported Model Exchange FMU features explicitly rather than silently ignoring them. | `cs-fmu-packager-project/requirements.md` |
| FR-013 | The tool shall generate a valid FMI model description for the packaged Co-Simulation FMU. | `cs-fmu-packager-project/requirements.md` |
| FR-014 | The tool shall preserve units, causality, variability, and descriptions for exposed variables when that metadata is available and unambiguous. | `cs-fmu-packager-project/requirements.md` |
| FR-015 | The tool shall detect missing internal variables referenced by the package specification. | `cs-fmu-packager-project/requirements.md` |
| FR-016 | The tool shall detect incompatible connection directions in the package specification. | `cs-fmu-packager-project/requirements.md` |
| FR-017 | The tool shall detect duplicate wrapper variable names before generating an FMU. | `cs-fmu-packager-project/requirements.md` |
| FR-018 | The tool shall support deterministic artifact naming. | `cs-fmu-packager-project/requirements.md` |
| FR-019 | The tool shall provide a command-line interface for packaging from a specification file. | `cs-fmu-packager-project/requirements.md` |
| FR-020 | The tool shall emit a machine-readable build report describing inputs, outputs, tool versions, solver policy, and warnings. | `cs-fmu-packager-project/requirements.md` |