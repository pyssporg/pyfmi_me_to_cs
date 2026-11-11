# Test Cases: ssp_spec

**Source file:** `tests/test_ssp_spec.py` (replaced `tests/test_spec_validation.py`)

## Test Classes

### TestSspParsing (5 tests)

| Test | Description | Related Requirement |
| --- | --- | --- |
| `test_valid_ssp_parses` | A valid complete `.ssp` package normalizes to `PackageSpec` | FR-002 |
| `test_fmus_extracted_into_workspace` | Embedded FMUs are extracted into the workspace | FR-002 |
| `test_missing_file` | Nonexistent `.ssp` raises a clear error | SPR-001 |
| `test_non_ssp_extension` | Non-`.ssp` input is rejected | SPR-001 |
| `test_not_a_zip` | Non-archive input is rejected | SPR-001 |
| `test_missing_system_structure` | Archive missing `SystemStructure.ssd` is rejected | SPR-001 |

### TestSspValidation (10 tests)

| Test | Description | Related Requirement |
| --- | --- | --- |
| `test_missing_component_source` | Component without `source` is rejected | VR-004, SPR-002 |
| `test_missing_fmu_member` | Component `source` not bundled in the archive is rejected | VR-004 |
| `test_unknown_component_in_connection` | Connection referencing unknown component is rejected | VR-004 |
| `test_boundary_connection_rejected` | System-level connection is rejected | VR-004 |
| `test_duplicate_connector_name` | Duplicate boundary variable names are rejected | FR-017, VR-005 |
| `test_invalid_connector_kind` | Invalid connector `kind` is rejected | VR-004 |
| `test_invalid_connector_type` | Invalid connector type is rejected | VR-004 |
| `test_connector_unknown_fmu` | Connector referencing unknown component is rejected | VR-004 |
| `test_malformed_connector_element_path` | Malformed `element` path is rejected | VR-004 |
| `test_step_size_gt_comm_step` | Step size > communication step is rejected | SR-004 |
| `test_comm_step_mismatch` | Mismatched solver/wrapper communication_step is rejected | FR-009 |

### TestVendorConfig (3 tests)

| Test | Description | Related Requirement |
| --- | --- | --- |
| `test_solver_and_algebraic_loop_config` | Solver/wrapper/loop policy parsed from the vendor annotation | SR-004, SR-006 |
| `test_unknown_annotation_ignored` | Foreign annotations are ignored; defaults apply | SR-004 |
| `test_invalid_solver_type` | Non-`fixed_step` solver type is rejected | SR-004 |

### TestBoundaryVariables (3 tests)

| Test | Description | Related Requirement |
| --- | --- | --- |
| `test_parameter_start_from_binding` | Parameter start value resolved from `ParameterValues` | FR-005 |
| `test_calculated_parameter_becomes_readable_output` | `calculatedParameter` connector is exposed as a readable output | IMP-029 |
| `test_no_connectors_means_empty_variables` | No connectors → mapper auto-discovery (IMP-013) | IMP-013, IMP-029 |