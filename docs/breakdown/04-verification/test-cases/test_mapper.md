# Test Cases: mapper

**Source file:** `tests/test_mapper.py`

## Tests (7)

| Test | Description | Related Requirement |
| --- | --- | --- |
| `test_basic_mapping` | Package two connected FMUs with input/output mapping | VR-002 |
| `test_unknown_variable_reference` | Nonexistent variable reference in connection raises `MappingError` | FR-015, VR-004 |
| `test_unknown_fmu_in_connection` | Connection referencing nonexistent FMU raises error | FR-015 |
| `test_parameter_mapping` | Parameter variable with start value is mapped correctly | FR-005 |
| `test_single_fmu_mapping` | Single FMU with input/output creates correct mapping with no algebraic loops | VR-001 |
| `test_algebraic_loop_detection_internal` | Two FMUs with feedback connections produce an algebraic loop detection | VR-008 |
| `test_mapping_with_non_real_types` | Integer/Boolean/String variable types are handled in mapping | C-004 |