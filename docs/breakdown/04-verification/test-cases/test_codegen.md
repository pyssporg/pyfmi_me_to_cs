# Test Cases: codegen

**Source file:** `tests/test_codegen.py`

## Test Classes

### TestCmakeCodegen (1 test)

| Test | Description | Related Requirement |
| --- | --- | --- |
| `test_generate_cmake` | CMakeLists.txt contains expected elements (cmake_minimum_required, find_package, sources, platform) | FR-013 |

### TestModelDescriptionCodegen (4 tests)

| Test | Description | Related Requirement |
| --- | --- | --- |
| `test_generate_model_description` | modelDescription.xml contains FMI version, CoSimulation element, solver policy, FMU mapping | VR-007 |
| `test_variable_preservation` | Wrapper inputs/outputs appear in modelDescription.xml with correct causality | VR-003 |
| `test_guid_deterministic` | GUID is deterministic from the same spec | NFR-001 |
| `test_non_real_type_xml` | Integer/Boolean/String variables produce correct XML sub-elements | C-004 |