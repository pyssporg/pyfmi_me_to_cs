# Module: errors

**File:** `src/cs_fmu_packager/errors.py`

## Responsibility

Custom exception hierarchy for the cs-fmu-packager tool. All exceptions inherit from `CsFmuPackagerError`.

## Exception Classes

| Exception | Raised By | Description |
| --- | --- | --- |
| `CsFmuPackagerError` | — | Base exception for all cs-fmu-packager errors |
| `SpecValidationError` | `spec.py` | Package specification is invalid |
| `FmuInspectionError` | `fmu_reader.py` | Internal FMU cannot be read or validated |
| `MappingError` | `mapper.py` | Variable mapping between spec and FMUs fails |
| `CodegenError` | `codegen/wrapper.py` | C code generation fails |
| `BuildError` | `builder.py` | CMake build of wrapper code fails |
| `PackagingError` | `packager.py` | Final FMU assembly fails |

## Exception Flow

All exceptions bubble up to `cli.py` → `main()` → caught and printed to stderr with exit code 1.

## Source

- `src/cs_fmu_packager/errors.py` (29 lines)