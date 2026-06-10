# Module: packager

**File:** `src/cs_fmu_packager/packager.py`

## Responsibility

FMU assembly and packaging. Assembles the final FMU ZIP archive with deterministic properties (sorted entries, fixed timestamps, no absolute paths).

## Key Functions

| Function | Description |
| --- | --- |
| `assemble_fmu(spec, mapping, so_path, output_path, ..., date_time=None)` | Assemble the final FMU ZIP archive; accepts optional `date_time` for non-deterministic timestamps via pyssp_standard `FMU.create()` pathway; returns `BuildReport` |
| `write_build_report(report, report_path)` | Write a machine-readable build report as JSON |
| `_make_zip_info(name)` | Create a ZipInfo with deterministic properties (fixed timestamp) |
| `_compute_checksum(path)` | Compute SHA-256 checksum of a file |
| `_assemble_fmu_via_pyssp(spec, mapping, so_path, output_path, fmu_name, date_time)` | Internal helper: assemble FMU using `FMU.create()` with resources and `set_generation_date_and_time()` |

## FMU Assembly Steps (Deterministic — default `date_time=None`)

1. Write `modelDescription.xml` (from `model_description.py`)
2. Write compiled `.so` to `binaries/linux64/<fmu_name>.so`
3. Embed internal ME FMUs in `resources/<fmu_id>.fmu`

## FMU Assembly Steps (Non-deterministic — `date_time` provided)

1. Write `modelDescription.xml` to temp file
2. Use `FMU.create(output_path, model_description=xml_path, binaries={"linux64": so_path})`
3. Open FMU in append mode, add internal FMUs via `add_resource()`
4. Call `FMU.set_generation_date_and_time(date_time)`

## Deterministic Properties

- ZIP entries use fixed timestamps (Jan 1, 2020 00:00:00) when `date_time` is None
- When `date_time` is provided, FMU.create pathway uses actual file timestamps
- All entries use ZIP_DEFLATED compression (both pathways)
- File permissions set to `0o644`

## Error Handling

- Validates `.so` file exists before assembly
- Validates all internal FMU files exist
- `OSError` and `zipfile.BadZipFile` are caught and wrapped in `PackagingError`

## Source

- `src/cs_fmu_packager/packager.py` (205 lines)

## Related Tests

- `tests/test_end_to_end.py` — `test_assembled_fmu_structure`, `test_deterministic_content`