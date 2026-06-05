# Non-Functional Requirements

| ID | Requirement | Source |
| --- | --- | --- |
| NFR-001 | Generated artifacts shall be reproducible from the same input specification and tool version. | `cs-fmu-packager-project/requirements.md` |
| NFR-002 | Error messages shall identify the failing package specification element. | `cs-fmu-packager-project/requirements.md` |
| NFR-003 | The tool shall avoid hidden network access during packaging. | `cs-fmu-packager-project/requirements.md` |
| NFR-004 | The generated FMU shall not depend on absolute source paths at runtime. | `cs-fmu-packager-project/requirements.md` |
| NFR-005 | The generated FMU shall keep runtime dependencies explicit. | `cs-fmu-packager-project/requirements.md` |
| NFR-006 | The implementation shall be testable without proprietary FMI tools. | `cs-fmu-packager-project/requirements.md` |
| NFR-007 | The project shall include small reference FMUs or generated test FMUs for automated tests. | `cs-fmu-packager-project/requirements.md` |
| NFR-008 | The initial implementation shall prioritize correctness and traceability over runtime performance. | `cs-fmu-packager-project/requirements.md` |
| NFR-009 | The wrapper architecture shall allow later optimization of variable lookup and solver execution. | `cs-fmu-packager-project/requirements.md` |