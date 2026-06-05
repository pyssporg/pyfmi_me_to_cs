# Initial Constraints

| ID | Constraint | Source |
| --- | --- | --- |
| C-001 | The first version may support fixed-step execution only. | `cs-fmu-packager-project/requirements.md` |
| C-002 | The first version may reject internal FMUs that require unsupported event handling. | `cs-fmu-packager-project/requirements.md` |
| C-003 | The first version may reject variable-step solver requirements. | `cs-fmu-packager-project/requirements.md` |
| C-004 | The first version may support a limited set of scalar Real variables before arrays, integers, booleans, and strings are generalized. | `cs-fmu-packager-project/requirements.md` |
| C-005 | The first version may treat advanced FMI features such as clocks, binary variables, and scheduled execution as out of scope. | `cs-fmu-packager-project/requirements.md` |

**Note**: These constraints are also recorded in `00-intent/constraints.md` with IDs CON-001 through CON-005 for PBS consistency.