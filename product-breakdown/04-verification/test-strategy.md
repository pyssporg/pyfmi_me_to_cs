# Test Strategy

## Overall Approach

Three-tier testing strategy:

1. **Unit tests** — Test individual pipeline phases in isolation using synthetic FMU files (generated ZIP archives with known content).
2. **Integration tests** — Test the full packaging pipeline end-to-end, including FMU assembly and deterministic output verification.
3. **Build tests** — Test CMake build execution (conditional on `VCPKG_ROOT` being set, as they require vcpkg + SUNDIALS).

## Test Layout

| File | Type | Tests | Coverage |
| --- | --- | --- | --- |
| `test_spec_validation.py` | Unit | 13 | Spec parsing, validation rules, error messages |
| `test_fmu_inspection.py` | Unit | 6 | FMU ZIP parsing, XML extraction, validation |
| `test_mapper.py` | Unit | 7 | Variable resolution, connection direction, SCC detection |
| `test_codegen.py` | Unit | 3 classes | CMake generation, model description, variable preservation |
| `test_end_to_end.py` | Integration | 4 | FMU assembly, build report, deterministic output |

## Key Design Decisions

- Tests avoid proprietary FMI tools — test FMUs are generated as in-memory ZIP files with minimal valid XML.
- Build tests are conditional (`@pytest.mark.skipif`) on `VCPKG_ROOT` being set to avoid CI failures on non-Linux or non-vcpkg environments.
- Spec validation tests use temporary TOML files written to disk, then parsed through the standard API.
- Mapper tests create temporary FMU files via `tempfile.mkstemp` and clean up via `shutil.rmtree`.