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

The packager consumes a **complete SSP package** (`.ssp`): a ZIP archive that embeds
its internal Model Exchange FMUs alongside a `SystemStructure.ssd` system structure
description document.

```text
my_system.ssp
├── SystemStructure.ssd          # SSP 1.0 system structure description
└── resources/
    ├── compressor.fmu           # internal Model Exchange FMU
    └── valve.fmu                # internal Model Exchange FMU
```

Create the `SystemStructure.ssd` (SSP 1.0):

```xml
<ssd:SystemStructureDescription
    xmlns:ssd="http://ssp-standard.org/SSP1/SystemStructureDescription"
    xmlns:ssc="http://ssp-standard.org/SSP1/SystemStructureCommon">
  <ssd:System name="System">
    <ssd:Connectors>
      <ssd:Connector element="compressor/speed" name="target_speed" kind="input" />
      <ssd:Connector element="valve/flow_rate"  name="flow_rate"   kind="output" />
    </ssd:Connectors>
    <ssd:Elements>
      <ssd:Component name="compressor" source="resources/compressor.fmu" />
      <ssd:Component name="valve"      source="resources/valve.fmu" />
    </ssd:Elements>
    <ssd:Connections>
      <ssd:Connection startElement="compressor" startConnector="outlet_pressure"
                      endElement="valve" endConnector="inlet_pressure" />
    </ssd:Connections>
  </ssd:System>
  <ssd:Annotations>
    <ssc:Annotation type="cs-fmu-packager">
      <Solver type="fixed_step" stepSize="1e-3" communicationStep="1e-3" />
      <Wrapper communicationStep="1e-3" />
    </ssc:Annotation>
  </ssd:Annotations>
</ssd:SystemStructureDescription>
```

Package it (plus the FMUs) into the archive:

```bash
zip -r my_system.ssp SystemStructure.ssd resources/
```

> **Note:** solver and wrapper configuration (step sizes, algebraic-loop
> iteration policy) is carried by the optional `cs-fmu-packager` vendor
> annotation and falls back to built-in defaults when absent. Every internal
> FMU input, output, and parameter is accessible at the packaged boundary —
> either through the system `<Connectors>` you declare, or automatically by
> default. This enables get/set and observation of all internal values from an
> external master (see [IMP-029](product-breakdown/06-evolution/done/IMP-029-ssp-ssd-input-format.md)).

Build the Co-Simulation FMU:

```bash
python -m cs_fmu_packager my_system.ssp
```

This produces `my_system.fmu`. Add `--verbose` to see the full pipeline output,
or `--dry-run` to validate the package and inspect FMUs without building.

## CLI Usage

```
python -m cs_fmu_packager [OPTIONS] SPEC
```

| Option | Description |
|--------|-------------|
| `SPEC` | Path to a complete SSP package (`.ssp`) archive — `SystemStructure.ssd` plus embedded FMUs (required argument) |
| `-o, --output FILE` | Output FMU path (default: `<spec_basename>.fmu`) |
| `-r, --report FILE` | Write a JSON build report to the given path |
| `--vcpkg-root DIR` | Path to a vcpkg installation (overrides `VCPKG_ROOT`) |
| `--step-size FLOAT` | Override the fixed-step size parsed from the vendor annotation |
| `--communication-step FLOAT` | Override the communication step parsed from the vendor annotation |
| `--dry-run` | Validate package and inspect FMUs without building |
| `-v, --verbose` | Enable diagnostic pipeline logging |
| `--help` | Show usage and exit |

## Documentation

- [cs-fmu-packager-project/README.md](cs-fmu-packager-project/README.md) — design intent, scope, and project overview
- [product-breakdown/](product-breakdown/) — full product breakdown structure (7 layers: intent, product, architecture, implementation, verification, operation, evolution)
- [product-breakdown/decision-log.md](product-breakdown/decision-log.md) — architecture decisions (AD-001 through AD-007)