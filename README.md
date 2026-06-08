# cs-fmu-packager

[![CI](https://github.com/pyssporg/pyfmi_me_to_cs/actions/workflows/test.yml/badge.svg)](https://github.com/pyssporg/pyfmi_me_to_cs/actions/workflows/test.yml)

Package one or more FMI 2.0 Model Exchange FMUs into a single FMI 2.0 Co-Simulation FMU.

The packaged FMU exposes a normal Co-Simulation interface to an external master algorithm,
while internally instantiating Model Exchange FMUs, connects their variables, advances them
with a configurable local solver, and exposes selected inputs, outputs, parameters, and status
information at the wrapper boundary.

For design intent, full scope, and architectural motivation, see
[cs-fmu-packager-project/README.md](cs-fmu-packager-project/README.md) and
[product-breakdown/00-intent/purpose.md](product-breakdown/00-intent/purpose.md).

## Prerequisites

| Dependency | Minimum Version | Notes |
|-----------|----------------|-------|
| Python | 3.10 | |
| CMake | 3.20 | Build system for the generated C wrapper |
| C compiler | — | gcc or clang (Linux x86_64, see [AD-006](product-breakdown/02-architecture/decisions/AD-006-linux-x86-64-v1.md)) |
| vcpkg      | —              | With [SUNDIALS](product-breakdown/02-architecture/decisions/AD-002-sundials-solver.md) installed (see [AD-007](product-breakdown/02-architecture/decisions/AD-007-vcpkg-package-manager.md)) |
| pyssp-standard | 0.8        | FMU metadata inspection (installed automatically via pip) |

## Installation

```bash
# Standard install
pip install .

# Editable (development) mode
pip install -e .
```

## Quickstart

Create a TOML specification file (e.g., `my_system.toml`):

```toml
[metadata]
identifier = "my_cs_fmu"

[fmus]
compressor = { path = "path/to/compressor.fmu" }
valve       = { path = "path/to/valve.fmu" }

[[connections]]
source = "compressor.outlet_pressure"
target = "valve.inlet_pressure"

[[variables]]
name       = "target_speed"
type       = "Real"
causality  = "input"
source     = "compressor.speed"

[[variables]]
name       = "flow_rate"
type       = "Real"
causality  = "output"
target     = "valve.flow_rate"

[solver]
type              = "fixed_step"
step_size         = 1e-3
communication_step = 1e-3

[wrapper]
communication_step = 1e-3
```

> **Note:** The `[[variables]]` section is optional. If omitted, all FMU inputs,
> outputs, and parameters are automatically exposed as wrapper boundary variables
> (see [IMP-013](product-breakdown/06-evolution/candidates/IMP-013.md)).

Build the Co-Simulation FMU:

```bash
python -m cs_fmu_packager my_system.toml
```

This produces `my_system.fmu`. Add `--verbose` to see the full pipeline output,
or `--dry-run` to validate the spec and inspect FMUs without building.

## CLI Usage

```
python -m cs_fmu_packager [OPTIONS] SPEC
```

| Option | Description |
|--------|-------------|
| `SPEC` | Path to a TOML package specification file (required argument) |
| `-o, --output FILE` | Output FMU path (default: `<spec_basename>.fmu`) |
| `-r, --report FILE` | Write a JSON build report to the given path |
| `--vcpkg-root DIR` | Path to a vcpkg installation (overrides `VCPKG_ROOT`) |
| `--dry-run` | Validate spec and inspect FMUs without building |
| `-v, --verbose` | Enable diagnostic pipeline logging |
| `--help` | Show usage and exit |

## Documentation

- [cs-fmu-packager-project/README.md](cs-fmu-packager-project/README.md) — design intent, scope, and project overview
- [product-breakdown/](product-breakdown/) — full product breakdown structure (7 layers: intent, product, architecture, implementation, verification, operation, evolution)
- [product-breakdown/decision-log.md](product-breakdown/decision-log.md) — architecture decisions (AD-001 through AD-007)