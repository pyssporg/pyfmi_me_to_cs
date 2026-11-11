# Module: codegen/cmake

**File:** `src/cs_fmu_packager/codegen/cmake.py`

## Responsibility

Generates `CMakeLists.txt` for the wrapper build system. Configures CMake with SUNDIALS dependency, FMI headers, and Linux-only platform check.

## Key Functions

| Function | Description |
| --- | --- |
| `generate_cmake(mapping, spec)` | Generate CMakeLists.txt content |

## Generated Build Configuration

- CMake minimum version: 3.22
- C standard: C11
- Position-independent code enabled (for `.so`)
- Finds SUNDIALS packages: `arkode`, `nvecserial`
- Includes directories: FMI C headers, generated wrapper headers, SUNDIALS headers
- Links: `SUNDIALS::arkode`, `SUNDIALS::nvecserial`
- Output: `binaries/linux64/<fmu_name>.so` (no `lib` prefix)
- Platform check: rejects non-Linux with error

## Source Files (in CMakeLists.txt)

- `fmi2_interface.c`
- `solver_integration.c`
- `fixed_point_iteration.c`

## Source

- `src/cs_fmu_packager/codegen/cmake.py` (72 lines)

## Related Tests

- `tests/test_codegen.py` — `TestCmakeCodegen` class