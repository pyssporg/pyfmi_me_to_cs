# Component View

## 6-Phase Pipeline

The cs-fmu-packager operates as a sequential six-phase pipeline:

```
Phase 1:     Phase 2:     Phase 3:     Phase 4:     Phase 5:     Phase 6:
Spec Parse → FMU Inspect →  Mapping   → Codegen   →  Build     →  Package
(spec.py)   (fmu_reader.py) (mapper.py) (codegen/)  (builder.py) (packager.py)
```

## Module Responsibility Map

| Module | Phase | Responsibility |
| --- | --- | --- |
| `cli.py` | All (orchestrator) | CLI entry point, argument parsing, pipeline orchestration, error handling |
| `spec.py` | 1 | TOML parsing, field validation, error collection (all errors before raising) |
| `fmu_reader.py` | 2 | ZIP archive opening, modelDescription.xml parsing, variable extraction, feature detection |
| `models.py` | 1–3, 6 | Dataclass definitions: PackageSpec, MappingTable, BuildReport (FmuMetadata/ScalarVariable removed, delegated to pyssp_standard) |
| `mapper.py` | 2–3 | Variable reference resolution, connection direction validation, SCC detection + execution order (pyssp_standard connection_graph delegate) |
| `codegen/__init__.py` | 4 | Codegen sub-package marker |
| `codegen/wrapper.py` | 4 | Orchestrates generation of all C source files, CMakeLists.txt, and modelDescription.xml |
| `codegen/fmi_interface.py` | 4 | Generates `fmi2_interface.c` — FMI 2.0 CS entry points, variable mapping, dlsym-based FMU loading |
| `codegen/solver.py` | 4 | Generates `solver_integration.c` — SUNDIALS ARKODE fixed-step integrator |
| `codegen/fixed_point.py` | 4 | Generates `fixed_point_iteration.c` — fixed-point algebraic loop solver |
| `codegen/cmake.py` | 4 | Generates `CMakeLists.txt` — build system with SUNDIALS linkage |
| `model_description.py` | 4, 6 | Generates `modelDescription.xml` — FMI 2.0 CS model description with annotations |
| `builder.py` | 5 | CMake configure/build orchestration, tool version capture, .so path resolution |
| `packager.py` | 6 | FMU ZIP assembly with deterministic metadata (fixed timestamps, sorted entries) or pyssp_standard FMU.create() pathway with date_time, build report |
| `errors.py` | All | Custom exception hierarchy: SpecValidationError, FmuInspectionError, MappingError, CodegenError, BuildError, PackagingError |