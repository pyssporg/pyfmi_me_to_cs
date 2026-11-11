# Configuration

> **Canonical source:** the complete, user-facing configuration reference
> (vendor annotation schema, solver types, runtime solver parameters,
> precedence, defaults) is [`docs/CONFIGURATION.md`](../../docs/CONFIGURATION.md).
> This page documents the packaging configuration surfaces for the
> product-breakdown structure.

## SSP Package Specification

The primary configuration input is a complete SSP package (`.ssp`) — a ZIP archive containing `SystemStructure.ssd` and the embedded internal FMUs (see `modules/ssp_spec.md`):

- `SystemStructure` attributes — name/version → `metadata.identifier`
- `<Components>` — internal FMU references (name → source URI inside the archive)
- `<Connections>` — source/target variable pairs (`startElement`/`startConnector` → `endElement`/`endConnector`)
- `<Connectors>` — boundary variables (edge wiring); optional — auto-discovered from FMU files when absent (IMP-013)
- vendor `<Annotations>` (`cs-fmu-packager`) — solver type, step sizes, tolerance, algebraic_loop config, wrapper communication_step (schema in `docs/CONFIGURATION.md`)

## pyproject.toml

Python package configuration:
- Package name: `cs-fmu-packager`
- Version: `0.1.1`
- Python: `>=3.10`
- Dependencies: `click>=8.0`, `pyssp-standard>=0.8` (SSP 1.0 SSD + FMI metadata); `toml` removed with the TOML front-end (IMP-029)
- Entry point: `cs-fmu-packager = "cs_fmu_packager.cli:main"`

## CMakePresets.json

CMake build presets for the packaging host:
- Default configure preset: Unix Makefiles, Release type, vcpkg toolchain
- Default build preset: links to default configure preset

## vcpkg.json

vcpkg dependency manifest:
- Dependency: `sundials`
- Built-in baseline for reproducible dependency resolution