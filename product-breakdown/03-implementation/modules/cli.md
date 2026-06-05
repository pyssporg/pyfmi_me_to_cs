# Module: cli

**File:** `src/cs_fmu_packager/cli.py`

## Responsibility

CLI entry point and pipeline orchestration. Provides a `click`-based command-line interface accepting a spec file path, output path, and various options. Orchestrates the six-phase pipeline: parse → inspect → map → codegen → build → package.

## Key Functions

| Function | Description |
| --- | --- |
| `main()` | Click command entry point; delegates to `_execute()` |
| `_execute()` | Internal pipeline execution: parse spec → build mapping → dry-run check → codegen → build → package → write report |

## CLI Options

| Option | Description |
| --- | --- |
| `SPEC` (positional) | Path to TOML package specification file |
| `-o, --output` | Output FMU path (default: `<spec_name>.fmu`) |
| `-r, --report` | Build report JSON output path |
| `--vcpkg-root` | Path to vcpkg installation |
| `--dry-run` | Validate spec + inspect FMUs only (no build) |
| `-v, --verbose` | Enable diagnostic logging |

## Error Handling

All pipeline exceptions inherit from `CsFmuPackagerError` and are caught at the `main()` level, printed to stderr, and exit with code 1.

## Source

- `src/cs_fmu_packager/cli.py` (220 lines)

## Related Tests

- `tests/test_end_to_end.py` — `test_dry_run_validates_spec`