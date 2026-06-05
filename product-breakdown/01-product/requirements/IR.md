# Initialization Requirements

| ID | Requirement | Source |
| --- | --- | --- |
| IR-001 | The wrapper shall initialize internal FMUs in a deterministic order. | `cs-fmu-packager-project/requirements.md` |
| IR-002 | The wrapper shall apply configured start values before completing initialization. | `cs-fmu-packager-project/requirements.md` |
| IR-003 | The wrapper shall validate required wrapper parameters before entering simulation mode. | `cs-fmu-packager-project/requirements.md` |
| IR-004 | The wrapper shall document how initial values for internal loop states are chosen. | `cs-fmu-packager-project/requirements.md` |
| IR-005 | Initialization failures from internal FMUs shall be propagated to the wrapper user. | `cs-fmu-packager-project/requirements.md` |