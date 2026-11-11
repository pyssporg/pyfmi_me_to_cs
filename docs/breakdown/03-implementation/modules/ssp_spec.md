# Module: ssp_spec

**File:** `src/cs_fmu_packager/ssp_spec.py` (replaced `spec.py`)

## Responsibility

SSP package specification parsing and normalization. Reads a **complete SSP package** (`.ssp`) — a ZIP archive containing `SystemStructure.ssd` and the embedded internal FMUs — extracts the embedded FMUs into a caller-owned workspace directory, validates all fields (components, connections, boundary connectors, vendor solver/wrapper policy), and returns a validated `PackageSpec` dataclass. All validation errors are collected before raising `SpecValidationError`.

XML handling is delegated to the `pyssp_standard` SSP 1.0 stack (`Ssp1SsdCodec`); this module provides the normalization layer from `Ssd1SystemStructureDescription` to the packaging pipeline's `PackageSpec`.

## Key Functions

| Function | Description |
| --- | --- |
| `parse_spec(path, workspace_dir=None)` | Parse and validate a complete `.ssp` archive; extracts embedded FMUs into `workspace_dir`; returns `PackageSpec` |
| `_parse_ssd(xml_text)` | Tolerant SSD parse (namespace-remaps onto the codec's namespace) |
| `_extract_fmu()` | Extract one embedded FMU component from the archive into the workspace |
| `_normalize_connector()` | Map a system-level connector to a boundary `WrapperVariable` (edge wiring) |
| `_normalize_connection()` | Map an SSD connection to a packaging `Connection` |
| `_parse_vendor_config()` | Read solver/wrapper policy from the `cs-fmu-packager` annotation (defaults fallback) |

## Normalization Rules

- **Components**: `<Component source="...">` (type `application/x-fmu-sharedlibrary`) → `FmuRef`; `source` is a relative URI resolved inside the archive; the FMU bytes are extracted to `<workspace>/<name>.fmu`.
- **Connections**: `<Connection startElement endElement startConnector endConnector>` → `Connection`. System-level (boundary) connections are rejected — the boundary is expressed through system connectors.
- **Boundary variables (edge wiring)**: system `<Connectors>` → `WrapperVariable`; `kind` maps to causality (`input`→`input`, `output`→`output`, `parameter`→`parameter`, `calculatedParameter`→readable `output`, `inout`→`input`). Start values come from `<ParameterBindings>`/`<ParameterValues>`.
- **Configuration**: solver/wrapper policy is carried by a vendor `<Annotations>` block (`type="cs-fmu-packager"`) with `Solver`/`AlgebraicLoop`/`Wrapper` elements; falls back to packaging defaults when absent. The full schema, supported solver types, and defaults are documented in `docs/CONFIGURATION.md`. Validation constraints: solver type must be one of the supported types, `step_size ≤ communication_step`, `solver.communication_step == wrapper.communication_step`.
- Component names must be unique; connector (boundary variable) names must be unique; connectors reference existing components.

## Source

- `src/cs_fmu_packager/ssp_spec.py` (replaced `src/cs_fmu_packager/spec.py`, which was removed with the TOML front-end)

## Related Tests

- `tests/test_ssp_spec.py` — 23 tests covering valid packages, extraction, missing members, invalid connectors/connections, vendor configuration, and boundary variables (replaced `tests/test_spec_validation.py`)