# Module: packager

**File:** `src/cs_fmu_packager/packager.py`

## Responsibility

FMU assembly and packaging. Assembles the final FMU ZIP archive with deterministic properties (sorted entries, fixed timestamps, no absolute paths).

## Key Functions

| Function | Description |
| --- | --- |
| `assemble_fmu(spec, mapping, so_path, output_path, ...)` | Assemble the final FMU ZIP archive; returns `BuildReport` |
| `write_build_report(report, report_path)` | Write a machine-readable build report as JSON |
| `_make_zip_info(name)` | Create a ZipInfo with deterministic properties (fixed timestamp) |
| `_compute_checksum(path)` | Compute SHA-256 checksum of a file |

## FMU Assembly Steps

1. Write `modelDescription.xml` (from `model_description.py`)
2. Write compiled `.so` to `binaries/linux64/<fmu_name>.so`
3. Embed internal ME FMUs in `resources/<fmu_id>.fmu`

## Deterministic Properties

- ZIP entries use fixed timestamps (Jan 1, 2020 00:00:00)
- All entries use ZIP_DEFLATED compression
- File permissions set to `0o644`
- `modelDescription.xml` generation timestamp is the only non-deterministic element

## Error Handling

- Validates `.so` file exists before assembly
- Validates all internal FMU files exist
- `OSError` and `zipfile.BadZipFile` are caught and wrapped in `PackagingError`

## Source

- `src/cs_fmu_packager/packager.py` (157 lines)

## Related Tests

- `tests/test_end_to_end.py` — `test_assembled_fmu_structure`, `test_deterministic_content`