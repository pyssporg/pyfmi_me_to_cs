# Test Cases: fmu_inspection

**Source file:** `tests/test_fmu_inspection.py`

## Test Classes

### TestFmuInspection (6 tests)

| Test | Description | Related Requirement |
| --- | --- | --- |
| `test_inspect_valid_fmu` | A valid ME FMU is inspected correctly; metadata matches expected values | FR-006 |
| `test_inspect_nonexistent_fmu` | Nonexistent file raises `FmuInspectionError` | NFR-002 |
| `test_inspect_not_a_zip` | Invalid file (not a ZIP) raises `FmuInspectionError` | NFR-002 |
| `test_inspect_missing_model_desc` | FMU without `modelDescription.xml` raises error | FR-013 |
| `test_inspect_wrong_fmi_version` | FMI 1.0 FMU is rejected | CR-002 |
| `test_inspect_not_me_fmu` | Co-Simulation-only FMU is rejected | CR-002 |