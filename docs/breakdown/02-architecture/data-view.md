# Data View

## Primary Data Entities

| Entity | Description | Owner | Created In |
| --- | --- | --- | --- |
| `PackageSpec` | Parsed and validated package specification from a complete SSP (`.ssp`) archive | `ssp_spec.py` | Phase 1 |
| `Fmi2ModelDescriptionDocument` | Metadata extracted from an FMU's modelDescription.xml | `fmu_reader.py` | Phase 2 |
| `MappingTable` | Resolved mapping: variables, connections, algebraic loops, execution order | `mapper.py` | Phase 3 |
| Generated C source files | `fmi2_interface.c`, `solver_integration.c`, `fixed_point_iteration.c` | `codegen/*.py` | Phase 4 |
| `CMakeLists.txt` | CMake build configuration | `codegen/cmake.py` | Phase 4 |
| `modelDescription.xml` | FMI 2.0 Co-Simulation model description for output FMU | `model_description.py` | Phase 4, 6 |
| `BuildResult` | Build outcome: .so path, tool versions, architecture info | `builder.py` | Phase 5 |
| `BuildReport` | Machine-readable packaging summary | `packager.py` | Phase 6 |
| `.fmu` file | Final ZIP archive containing modelDescription.xml, .so, resources/ | `packager.py` | Phase 6 |

## Ownership Boundaries

- **Spec-level data** is owned by the Python CLI process and never embedded in the generated FMU beyond metadata annotations.
- **FMU-level data** (internal FMU archives) is embedded as byte-for-byte copies in `resources/` inside the generated FMU (see AD-004).
- **Generated C code** is compiled into the `.so` shared library and is not user-visible after packaging (unless the user extracts the FMU).
- **Build report** is optionally written as a JSON file for external consumption; it is not part of the FMU archive.

## Data Flow

```
SSP (.ssp) archive ──→ parse_spec() ──→ PackageSpec ──→ inspect_fmu() ──→ Fmi2ModelDescriptionDocument
                                                                    │
                                          PackageSpec + FmuMetadata │
                                                                    ▼
                                                            build_mapping()
                                                                    │
                                                                    ▼
                                                            MappingTable
                                                                    │
                                         PackageSpec + MappingTable │
                                                                    ▼
                                         ┌──────────────────────────┐
                                         │    codegen/wrapper.py    │
                                         │    (generate_all)        │
                                         └──────┬──────────┬────────┘
                                                │          │
                                                ▼          ▼
                                    C source files    modelDescription.xml
                                                │          │
                                                ▼          │
                                          builder.py       │
                                          (CMake build)    │
                                                │          │
                                                ▼          ▼
                                          packager.py (assemble_fmu)
                                                │
                                                ▼
                                          .fmu file + BuildReport
```