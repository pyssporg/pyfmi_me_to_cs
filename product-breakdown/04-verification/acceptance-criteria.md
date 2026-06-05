# Acceptance Criteria

| ID | Criterion | Verification Method |
| --- | --- | --- |
| AC-001 | A valid TOML spec with one FMU, one connection, and two wrapper variables produces a valid `.fmu` file. | `test_end_to_end.py::test_assembled_fmu_structure` |
| AC-002 | An invalid spec (missing section, bad reference, duplicate name) produces a clear error message identifying the failing element. | `test_spec_validation.py` (all 13 tests) |
| AC-003 | Two FMUs with feedback connections are correctly detected as an algebraic loop. | `test_mapper.py::test_algebraic_loop_detection_internal` |
| AC-004 | The generated `modelDescription.xml` contains solver policy, internal FMU list, and wrapper variable declarations. | `test_codegen.py::TestModelDescriptionCodegen::test_generate_model_description` |
| AC-005 | The same spec produces the same generated artifact structure (deterministic content). | `test_codegen.py::TestModelDescriptionCodegen::test_guid_deterministic`; `test_end_to_end.py::test_deterministic_content` |
| AC-006 | A Co-Simulation-only FMU (not Model Exchange) is rejected with an appropriate error. | `test_fmu_inspection.py::test_inspect_not_me_fmu` |
| AC-007 | Non-Linux platforms produce a clear error during CMake configuration (v1 constraint). | CMakeLists.txt platform check (tested via CMake test) |