# Quality Attributes

| ID | Attribute | Description | Related NFR |
| --- | --- | --- | --- |
| QA-001 | Reproducibility | Generated FMU artifacts are deterministic from the same specification and tool version, enabling reproducible experiments. | NFR-001 |
| QA-002 | Correctness | The implementation prioritizes correctness and traceability over runtime performance. Error messages identify the failing specification element. | NFR-008, NFR-002 |
| QA-003 | Self-Containment | The generated FMU has no runtime dependencies on absolute paths or network access. All internal FMUs are embedded. | NFR-003, NFR-004 |
| QA-004 | Explicit Dependencies | Runtime dependencies of the generated FMU are documented and explicit. No hidden or implicit dependencies. | NFR-005 |
| QA-005 | Testability | The implementation is testable without proprietary FMI tools. Small reference FMUs serve as test fixtures. | NFR-006, NFR-007 |
| QA-006 | Extensibility | The wrapper architecture allows later optimization of variable lookup and solver execution. Additional solvers can be added without changing unrelated spec elements. | NFR-009, SR-002 |