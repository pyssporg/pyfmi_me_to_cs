# Traceability Matrix: Requirements → Tests

| Requirement | Test(s) |
| --- | --- |
| VR-001: Package one scalar ME FMU | `test_mapper.py::test_single_fmu_mapping`, `test_end_to_end.py::test_assembled_fmu_structure` |
| VR-002: Package two connected ME FMUs | `test_mapper.py::test_basic_mapping`, `test_end_to_end.py::test_assembled_fmu_structure` |
| VR-003: Expose wrapper inputs/outputs with stable names | `test_codegen.py::TestModelDescriptionCodegen::test_variable_preservation` |
| VR-004: Invalid variable references → error | `test_spec_validation.py::test_invalid_fmi_version`, `test_invalid_variable_type`, `test_invalid_fmu_ref_format`, `test_unknown_fmu_in_connection`; `test_mapper.py::test_unknown_variable_reference`, `test_unknown_fmu_in_connection` |
| VR-005: Duplicate wrapper variable names → error | `test_spec_validation.py::test_duplicate_variable_name` |
| VR-006: Solver failure reporting | `test_end_to_end.py::TestEndToEndWithBuild` (conditional on VCPKG_ROOT) |
| VR-007: Metadata contains solver policy and internal FMU mapping | `test_codegen.py::TestModelDescriptionCodegen::test_generate_model_description`; `test_end_to_end.py::TestBuildReport::test_report_content` |
| VR-008: SCC packaging regression test | `test_mapper.py::test_algebraic_loop_detection_internal` |

## Additional Requirement Coverage

| Requirement | Test(s) |
| --- | --- |
| FR-002: Accept declarative spec | `test_spec_validation.py::test_valid_spec_parses` |
| FR-005: Expose parameters | `test_mapper.py::test_parameter_mapping` |
| FR-015: Detect missing variable references | `test_mapper.py::test_unknown_variable_reference` |
| FR-016: Detect incompatible connection directions | `test_mapper.py::test_basic_mapping` (direction validation) |
| FR-017: Detect duplicate variable names | `test_spec_validation.py::test_duplicate_variable_name` |
| FR-019: CLI interface | `test_end_to_end.py::test_dry_run_validates_spec` |
| FR-020: Machine-readable build report | `test_end_to_end.py::TestBuildReport::test_report_content` |
| NFR-001: Deterministic artifacts | `test_codegen.py::TestModelDescriptionCodegen::test_guid_deterministic`; `test_end_to_end.py::test_deterministic_content` |
| NFR-002: Error messages identify element | All validation tests check error messages contain field names |
| C-004: Limited scalar types | `test_spec_validation.py::test_integer_type_accepted`, `test_boolean_type_accepted`, `test_string_type_accepted`; `test_mapper.py::test_mapping_with_non_real_types`; `test_codegen.py::TestModelDescriptionCodegen::test_non_real_type_xml` |