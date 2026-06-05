# Constraints

| ID | Constraint | Source |
| --- | --- | --- |
| CON-001 | The first version may support fixed-step execution only. | C-001 in `cs-fmu-packager-project/requirements.md` |
| CON-002 | The first version may reject internal FMUs that require unsupported event handling. | C-002 in `cs-fmu-packager-project/requirements.md` |
| CON-003 | The first version may reject variable-step solver requirements. | C-003 in `cs-fmu-packager-project/requirements.md` |
| CON-004 | The first version may support a limited set of scalar Real variables before arrays, integers, booleans, and strings are generalized. | C-004 in `cs-fmu-packager-project/requirements.md` |
| CON-005 | The first version may treat advanced FMI features such as clocks, binary variables, and scheduled execution as out of scope. | C-005 in `cs-fmu-packager-project/requirements.md` |

**Note**: Original IDs C-001 through C-005 have been renamed to CON-001 through CON-005 for consistency with the PBS naming convention.