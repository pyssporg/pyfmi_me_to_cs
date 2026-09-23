# cs-fmu-packager

[![CI](https://github.com/pyssporg/pyfmi_me_to_cs/actions/workflows/test.yml/badge.svg)](https://github.com/pyssporg/pyfmi_me_to_cs/actions/workflows/test.yml)

Convert a complete SSP package (`.ssp`) — one or more FMI 2.0 Model Exchange FMUs wired
together in a `SystemStructure.ssd` — into a single FMI 2.0 Co-Simulation FMU (`.fmu`).

```
SSP package (.ssp) ──► cs-fmu-packager ──► Co-Simulation FMU (.fmu)
```

The output CS FMU exposes a normal Co-Simulation interface to an external master algorithm,
while internally instantiating the packaged Model Exchange FMUs, connecting their variables,
advancing them with a configurable local solver, and exposing selected inputs, outputs,
parameters, and status information at the wrapper boundary. The internal connections and
algebraic loops are resolved at every integrator stage, so the grouped FMUs are solved as
one coupled equation system behind the single boundary (see
[docs/COUPLING_SEMANTICS.md](docs/COUPLING_SEMANTICS.md)).

For design intent, full scope, and architectural motivation, see
[product-breakdown/00-intent/purpose.md](product-breakdown/00-intent/purpose.md) and
[product-breakdown/README.md](product-breakdown/README.md).

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

> **Note:** solver and wrapper configuration (solver type, step sizes,
> tolerance, algebraic-loop iteration policy) is carried by the optional
> `cs-fmu-packager` vendor annotation and falls back to built-in defaults when
> absent. Every internal FMU input, output, and parameter is accessible at the
> packaged boundary — either through the system `<Connectors>` you declare, or
> automatically by default. This enables get/set and observation of all
> internal values from an external master (see
> [IMP-029](product-breakdown/06-evolution/done/IMP-029-ssp-ssd-input-format.md)).
> The complete configuration reference is in
> [docs/CONFIGURATION.md](docs/CONFIGURATION.md), and a fully runnable example
> is in [examples/quickstart](examples/quickstart/README.md).

Build the Co-Simulation FMU:

```bash
python -m cs_fmu_packager my_system.ssp
```

This produces `my_system.fmu`. Add `--verbose` to see the full pipeline output,
or `--dry-run` to validate the package and inspect FMUs without building.

## How It Works

The packager runs a six-phase pipeline from the input `.ssp` to the output CS FMU:

1. **Parse** — read `SystemStructure.ssd` from the archive and extract the embedded
   Model Exchange FMUs (see `product-breakdown/03-implementation/modules/ssp_spec.md`).
2. **Inspect** — read each internal FMU's `modelDescription.xml`.
3. **Map** — resolve boundary connectors and internal connections to FMU variables,
   detect algebraic loops, and compute the execution order.
4. **Codegen** — generate a C wrapper that instantiates the FMUs, wires their
   variables, and runs the configured local solver.
5. **Build** — compile the wrapper into a shared library with CMake + vcpkg/SUNDIALS.
6. **Package** — assemble the library, embedded FMUs, and a fresh
   `modelDescription.xml` into the output Co-Simulation FMU.

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
| `--c-headers DIR` | Path to a directory containing the FMI 2.0 C headers (default: auto-detect from package data) |
| `--step-size FLOAT` | Override the fixed-step size parsed from the vendor annotation |
| `--communication-step FLOAT` | Override the communication step parsed from the vendor annotation |
| `--dry-run` | Validate package and inspect FMUs without building |
| `-v, --verbose` | Enable diagnostic pipeline logging |
| `--help` | Show usage and exit |

## Documentation

- [docs/](docs/README.md) — user-facing documentation index
- [docs/CONFIGURATION.md](docs/CONFIGURATION.md) — full configuration reference (vendor annotation schema, solver types, runtime solver parameters, defaults)
- [docs/COUPLING_SEMANTICS.md](docs/COUPLING_SEMANTICS.md) — what the packaged FMU solves: one boundary, one coupled equation system, and how internal coupling is evaluated
- [examples/quickstart](examples/quickstart/README.md) — runnable example (build + simulate)
- [GETTING_STARTED.md](GETTING_STARTED.md) — step-by-step walkthrough
- [product-breakdown/00-intent/purpose.md](product-breakdown/00-intent/purpose.md) — design intent, scope, and project overview
- [product-breakdown/](product-breakdown/) — full product breakdown structure (7 layers: intent, product, architecture, implementation, verification, operation, evolution)
- [product-breakdown/decision-log.md](product-breakdown/decision-log.md) — architecture decisions (AD-001 through AD-007)