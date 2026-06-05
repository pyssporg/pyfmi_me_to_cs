# Test Cases: spec_validation

**Source file:** `tests/test_spec_validation.py`

## Test Classes

### TestSpecParsing (13 tests)

| Test | Description | Related Requirement |
| --- | --- | --- |
| `test_valid_spec_parses` | A valid spec with all sections parses without errors | FR-002 |
| `test_missing_fmus_section` | Missing `[fmus]` raises error | SPR-001 |
| `test_missing_connections_section` | Missing `[[connections]]` raises error | SPR-003 |
| `test_invalid_fmi_version` | FMI version other than 2.0 is rejected | VR-004, SPR-002 |
| `test_invalid_variable_type` | Invalid variable type is rejected | VR-004 |
| `test_duplicate_variable_name` | Duplicate wrapper variable names are detected and rejected | FR-017, VR-005 |
| `test_step_size_greater_than_comm_step` | Step size > communication step is rejected | SR-004 |
| `test_invalid_fmu_ref_format` | Connection with invalid `source` format is rejected | VR-004 |
| `test_unknown_fmu_in_connection` | Connection referencing unknown FMU is rejected | VR-004 |
| `test_algebraic_loop_config` | Algebraic loop config (max_iterations, tolerance) is parsed correctly | SR-006 |
| `test_comm_step_mismatch` | Mismatched solver/wrapper communication_step is rejected | FR-009 |
| `test_integer_type_accepted` | Integer variable type is accepted | C-004 |
| `test_boolean_type_accepted` | Boolean variable type is accepted | C-004 |
| `test_string_type_accepted` | String variable type is accepted | C-004 |
| `test_invalid_start_type_for_real` | String start value for Real type is rejected | FR-005 |