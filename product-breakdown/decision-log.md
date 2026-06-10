# Decision Log

| ID | Title | Layer | Status | Location | Related artifacts |
| --- | --- | --- | --- | --- | --- |
| AD-001 | C Wrapper Architecture | Architecture | Accepted | `02-architecture/decisions/AD-001-c-wrapper-architecture.md` | `03-implementation/modules/codegen-fmi-interface.md`, `03-implementation/modules/codegen-solver.md`, `03-implementation/modules/builder.md`, `02-architecture/component-view.md` |
| AD-002 | SUNDIALS Solver | Architecture | Accepted | `02-architecture/decisions/AD-002-sundials-solver.md` | `03-implementation/modules/codegen-solver.md`, `02-architecture/integration-view.md`, `vcpkg.json`, `03-implementation/configuration.md` |
| AD-003 | Fixed-Point Iteration for Algebraic Loops | Architecture | Accepted | `02-architecture/decisions/AD-003-fixed-point-iteration.md` | `03-implementation/modules/codegen-fixed-point.md`, `03-implementation/modules/mapper.md`, `03-implementation/modules/models.md` |
| AD-004 | Embedded FMU Resources | Architecture | Accepted | `02-architecture/decisions/AD-004-embedded-fmu-resources.md` | `03-implementation/modules/packager.md`, `02-architecture/data-view.md`, `02-architecture/deployment-view.md` |
| AD-005 | TOML Spec Format | Architecture | Accepted | `02-architecture/decisions/AD-005-toml-spec-format.md` | `03-implementation/modules/spec.md`, `03-implementation/modules/models.md`, `04-verification/test-cases/test_spec_validation.md` |
| AD-006 | Linux x86_64 Only (v1) | Architecture | Accepted | `02-architecture/decisions/AD-006-linux-x86-64-v1.md` | `03-implementation/modules/builder.md`, `02-architecture/deployment-view.md`, `03-implementation/environments.md` |
| AD-007 | vcpkg Package Manager | Architecture | Accepted | `02-architecture/decisions/AD-007-vcpkg-package-manager.md` | `vcpkg.json`, `03-implementation/environments.md`, `03-implementation/configuration.md`, `03-implementation/modules/builder.md`, `03-implementation/modules/cli.md`, `02-architecture/integration-view.md`, `02-architecture/context-view.md`, `02-architecture/decisions/AD-002-sundials-solver.md`, `02-architecture/decisions/AD-006-linux-x86-64-v1.md` |
| AD-IMP-025-FORK | Fork Adoption | Implementation | Accepted | `06-evolution/candidates/IMP-025.md` | `fmu_reader.py`, `pyproject.toml` |
| AD-IMP-027-GRAPH | pyssp_standard connection_graph Delegate | Implementation | Candidate Accepted | `03-implementation/modules/mapper.md` | `src/cs_fmu_packager/mapper.py`, `03-implementation/candidates/IMP-027.md` |
