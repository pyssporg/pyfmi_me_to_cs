# Assumptions

| ID | Assumption | Source |
| --- | --- | --- |
| ASM-001 | The first motivating use case is strongly connected component grouping in a synthetic propagation benchmark. Each non-trivial SCC can be packaged as one Co-Simulation FMU. | `cs-fmu-packager-project/README.md` (Relationship To Synthetic Propagation Study) |
| ASM-002 | Input FMUs are FMI 2.0 Model Exchange, have valid modelDescription.xml, and their shared libraries can be loaded via dlopen. | `cs-fmu-packager-project/requirements.md` (CR-002), `src/cs_fmu_packager/fmu_reader.py` |
| ASM-003 | Build dependencies (CMake, GCC/Clang, vcpkg, SUNDIALS) are available on the packaging host. | `cs-fmu-packager-project/requirements.md` (OD-002), `src/cs_fmu_packager/builder.py` |
| ASM-004 | Generated FMUs are consumed on Linux x86_64 platforms in v1. | AD-006, `docs/decisions/AD-006-linux-x86-64-v1.md` |
| ASM-005 | The package specification text format (TOML) is suitable for version control and automated generation. | AD-005, `docs/decisions/AD-005-toml-spec-format.md` |
| ASM-006 | Algebraic loops can be resolved through fixed-point iteration within each communication step. | AD-003, `docs/decisions/AD-003-fixed-point-iteration.md` |