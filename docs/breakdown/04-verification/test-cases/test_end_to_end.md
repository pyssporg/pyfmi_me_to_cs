# Test Cases: end_to_end

**Source file:** `tests/test_end_to_end.py`

## Test Classes

### TestEndToEndWithBuild (conditional on VCPKG_ROOT)

| Test | Description | Related Requirement |
| --- | --- | --- |
| `test_dry_run_validates_spec` | Dry run validates spec without building | FR-019 |
| `test_assembled_fmu_structure` | Assembled FMU has correct ZIP structure (modelDescription.xml, binaries/, resources/) | VR-001, VR-002 |

### TestBuildReport

| Test | Description | Related Requirement |
| --- | --- | --- |
| `test_report_content` | Build report JSON has correct format and fields | FR-020, VR-007 |

### TestDeterministicAssembly

| Test | Description | Related Requirement |
| --- | --- | --- |
| `test_deterministic_content` | Same inputs produce same FMU structure and sorted entries | NFR-001 |