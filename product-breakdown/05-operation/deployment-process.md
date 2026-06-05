# Deployment Process

## Build Process

1. **Install build dependencies**: Python ≥3.10, CMake ≥3.22, GCC/Clang, vcpkg with SUNDIALS
2. **Install Python package**: `pip install .` (from repository root)
3. **Prepare package specification**: Create a `.toml` file describing internal FMUs, connections, variables, and solver
4. **Run packager**: `cs-fmu-packager spec.toml -o output.fmu`
5. **Consume generated FMU**: The `.fmu` file can be loaded by any FMI 2.0 Co-Simulation master algorithm

## Platform Constraint

The generated FMU is a Linux x86_64 `.so` shared library. It will only work on Linux x86_64 systems. See AD-006.

## Deterministic Builds

The FMU assembly uses fixed ZIP timestamps and sorted entry names. The `modelDescription.xml` contains a generation timestamp, so byte-level reproducibility requires comparing content structure (GUID, entries, sizes) rather than raw checksums.

## Source

Derived from `cs-fmu-packager-project/README.md` and `src/cs_fmu_packager/builder.py`.