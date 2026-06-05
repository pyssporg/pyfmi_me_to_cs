# Module: fmu_reader

**File:** `src/cs_fmu_packager/fmu_reader.py`

## Responsibility

FMU inspection and modelDescription.xml parsing. Opens an FMI 2.0 Model Exchange FMU archive, validates its structure, and extracts all metadata from modelDescription.xml.

## Key Functions

| Function | Description |
| --- | --- |
| `inspect_fmu(path)` | Open FMU archive, validate structure, parse XML, return `FmuMetadata` |
| `_parse_scalar_variables(root)` | Parse all ScalarVariable elements from modelDescription.xml |
| `_detect_unsupported_features(root)` | Detect features the wrapper does not support (e.g., event indicators, no get/set state) |

## Validation Checks

- File must exist and have `.fmu` extension
- Must be a valid ZIP archive
- Must contain `modelDescription.xml`
- FMI version must be `"2.0"`
- Must be a ModelExchange FMU (CoSimulation-only FMUs rejected)
- Unsupported features are detected and recorded in `FmuMetadata.unsupported_features`

## Source

- `src/cs_fmu_packager/fmu_reader.py` (208 lines)

## Related Tests

- `tests/test_fmu_inspection.py` — 6 tests covering valid FMU, nonexistent file, invalid ZIP, missing modelDescription, wrong FMI version, CS-only FMU rejection