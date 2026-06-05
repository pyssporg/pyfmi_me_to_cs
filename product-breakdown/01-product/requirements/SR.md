# Solver Requirements

| ID | Requirement | Source |
| --- | --- | --- |
| SR-001 | The initial solver set shall include a fixed-step explicit solver suitable for simple continuous-state Model Exchange FMUs. | `cs-fmu-packager-project/requirements.md` |
| SR-002 | The solver interface shall be designed so additional solvers can be added without changing package specifications unrelated to solver configuration. | `cs-fmu-packager-project/requirements.md` |
| SR-003 | The wrapper shall distinguish the outer communication step from any internal solver step. | `cs-fmu-packager-project/requirements.md` |
| SR-004 | The wrapper shall allow the internal solver step size to be equal to or smaller than the outer communication step. | `cs-fmu-packager-project/requirements.md` |
| SR-005 | The wrapper shall define and document its behavior for algebraic or direct-feedthrough loops. | `cs-fmu-packager-project/requirements.md` |
| SR-006 | If fixed-point iteration is supported, the wrapper shall expose maximum iteration count, tolerance, and convergence status. | `cs-fmu-packager-project/requirements.md` |
| SR-007 | If delayed-feedback loop handling is supported, the wrapper shall document the delay semantics and initialization values. | `cs-fmu-packager-project/requirements.md` |
| SR-008 | Solver failure shall be reported through FMI status codes and diagnostic log messages. | `cs-fmu-packager-project/requirements.md` |