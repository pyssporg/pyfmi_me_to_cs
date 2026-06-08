# Module: spec

**File:** `src/cs_fmu_packager/spec.py`

## Responsibility

Package specification parsing and validation. Reads a TOML spec file, validates all fields (FMU references, connections, variables, solver, wrapper), and returns a validated `PackageSpec` dataclass. All validation errors are collected before raising `SpecValidationError`.

## Key Functions

| Function | Description |
| --- | --- |
| `parse_spec(path)` | Parse and validate a TOML spec file; returns `PackageSpec` |
| `_validate_fmu_ref()` | Validate a single FMU reference entry |
| `_validate_connection()` | Validate a single connection entry |
| `_validate_variable()` | Validate a single wrapper variable entry |
| `_validate_solver()` | Validate the `[solver]` section |
| `_validate_wrapper()` | Validate the `[wrapper]` section |

## Validation Rules

- Required sections: `[fmus]`, `[[connections]]`, `[solver]`, `[wrapper]`; `[[variables]]` is optional (auto-discovered from FMU files when absent)
- FMU path must be present; FMI version must be `"2.0"`; kind must be `"ModelExchange"`
- Connections use `<fmu_id>.<variable_name>` syntax
- Variable names must be unique; causality must be `"input"`, `"output"`, or `"parameter"`
- Solver type must be `"fixed_step"` (v1 constraint); step_size ≤ communication_step
- `solver.communication_step` must equal `wrapper.communication_step`

## Source

- `src/cs_fmu_packager/spec.py` (349 lines)

## Related Tests

- `tests/test_spec_validation.py` — 13 tests covering valid specs, missing sections, invalid values, duplicate names, type validation