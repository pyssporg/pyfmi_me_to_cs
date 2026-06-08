# Configuration

## TOML Package Specification

The primary configuration input is a TOML file with the following sections:

- `[metadata]` — identifier, description, author, version (optional)
- `[fmus]` — internal FMU references (name → path, fmi_version, kind)
- `[[connections]]` — source/target variable pairs
- `[[variables]]` — wrapper boundary variables (name, type, causality, source/target, start); optional — auto-discovered from FMU files when absent
- `[solver]` — solver type, step_size, communication_step, algebraic_loop config
- `[wrapper]` — wrapper communication_step

## pyproject.toml

Python package configuration:
- Package name: `cs-fmu-packager`
- Version: `0.1.0`
- Python: `>=3.10`
- Dependencies: `click>=8.0`, `toml>=0.10`, `Jinja2>=3.0`, `pyssp-standard>=0.8`
- Entry point: `cs-fmu-packager = "cs_fmu_packager.cli:main"`

## CMakePresets.json

CMake build presets for the packaging host:
- Default configure preset: Unix Makefiles, Release type, vcpkg toolchain
- Default build preset: links to default configure preset

## vcpkg.json

vcpkg dependency manifest:
- Dependency: `sundials`
- Built-in baseline for reproducible dependency resolution