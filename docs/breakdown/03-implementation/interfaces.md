# Interfaces

## Pipeline Phase Contracts

Each phase in the 6-phase pipeline communicates through well-defined data structures from `models.py`:

| Phase | Input | Output | Module |
| --- | --- | --- | --- |
| 1. Spec Parse | complete SSP package (`.ssp`) path | `PackageSpec` | `ssp_spec.py` |
| 2. FMU Inspect | `FmuRef.path` (from PackageSpec, extracted workspace) | `Fmi2ModelDescriptionDocument` | `fmu_reader.py` |
| 3. Mapping | `PackageSpec` + inspected FMI docs | `MappingTable` | `mapper.py` |
| 4. Codegen | `PackageSpec` + `MappingTable` | Generated C source files, CMakeLists.txt, modelDescription.xml | `codegen/wrapper.py` |
| 5. Build | Source directory with generated files | `BuildResult` (so_path, tool_versions) | `builder.py` |
| 6. Package | `PackageSpec` + `MappingTable` + `BuildResult` | `.fmu` file + `BuildReport` | `packager.py` |

## Codegen Contract

`generate_all(spec, mapping, output_dir, c_headers_dir) → Dict[str, str]`

- Must produce `fmi2_interface.c`, `solver_integration.c`, `fixed_point_iteration.c`, `CMakeLists.txt`, `modelDescription.xml`
- Must copy FMI C headers into the output directory
- Raises `CodegenError` on failure

## Builder Interface

`build_fmu(source_dir, build_dir, vcpkg_root_arg, fmu_name, verbose) → BuildResult`

- Configures CMake with vcpkg toolchain
- Builds the generated C code
- Locates the resulting `.so`
- Raises `BuildError` on failure

## Packager Interface

`assemble_fmu(spec, mapping, so_path, output_path, fmu_name, build_metadata) → BuildReport`

- Creates a deterministic ZIP archive
- Writes modelDescription.xml, .so, and embedded FMUs
- Raises `PackagingError` on failure