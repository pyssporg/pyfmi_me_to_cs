# Getting Started with cs-fmu-packager

This guide walks you through your first Co-Simulation FMU build using cs-fmu-packager. By the end, you will have created a package spec, inspected your FMUs, built the packaged CS-FMU, and verified the output.

## Prerequisites

Before starting, install the following:

| Dependency | Minimum Version | Notes |
|------------|----------------|-------|
| Python     | 3.10           | |
| CMake      | 3.20           | Build system for generated C wrapper |
| C compiler | —              | gcc or clang (Linux x86_64 only; see [AD-006](product-breakdown/02-architecture/decisions/AD-006-linux-x86-64-v1.md)) |
| vcpkg      | —              | With SUNDIALS installed (see [AD-007](product-breakdown/02-architecture/decisions/AD-007-vcpkg-package-manager.md)) |

To install SUNDIALS via vcpkg:
```bash
git clone https://github.com/Microsoft/vcpkg.git
cd vcpkg && ./bootstrap-vcpkg.sh
./vcpkg install sundials
export VCPKG_ROOT="$PWD"
```

## Installation

Install the packager from a local clone or directly from source:

```bash
# From a local clone
pip install .

# Editable (development) mode
pip install -e ".[dev]"

# Verify it works
python -m cs_fmu_packager --help
```

## Quickstart Walkthrough

### Step 1: Create an SSP package

The input to cs-fmu-packager is a **complete SSP package** (`.ssp`) — a ZIP
archive embedding the internal Model Exchange FMUs alongside a
`SystemStructure.ssd` system structure description. Create a directory:

```text
my_system/
├── SystemStructure.ssd
└── resources/
    ├── compressor.fmu
    └── valve.fmu
```

With `SystemStructure.ssd`:

```xml
<ssd:SystemStructureDescription
    xmlns:ssd="http://ssp-standard.org/SSP1/SystemStructureDescription">
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
</ssd:SystemStructureDescription>
```

Then package it:

```bash
cd my_system && zip -r ../my_system.ssp SystemStructure.ssd resources/
```

> **Note:** every internal FMU input, output, and parameter is exposed at the
> packaged boundary — through the declared `<Connectors>` or automatically by
> default — so all internal values can be get/set/viewed by an external master.
> Fixed-step and communication step sizes come from the optional
> `cs-fmu-packager` vendor `<Annotations>` block, or fall back to defaults.

### Step 2: Validate your package (dry run)

```bash
python -m cs_fmu_packager my_system.ssp --dry-run
```

This validates the SSP package and inspects the embedded FMU files without
building anything. You should see output like:

```
Dry run: spec validated and FMUs inspected successfully.
  Execution order: compressor -> valve
  Algebraic loops: 0
```

If you see errors, check the SSD for typos and verify the FMU `source` URIs
match members inside the archive.

### Step 3: Build the Co-Simulation FMU

```bash
python -m cs_fmu_packager my_system.ssp
```

The tool will:
1. Parse `SystemStructure.ssd` and validate the package
2. Extract and inspect each internal FMU's modelDescription.xml
3. Map boundary variables to internal FMU variables
4. Generate C wrapper source code
5. Compile the wrapper using CMake and your C compiler
6. Package everything into a single FMU file

On success you will see:

```
Successfully created: my_system.fmu
  2 FMU(s), 2 variable(s), 1 connection(s)
```

### Step 4: Verify the output

Your packaged Co-Simulation FMU is at `my_system.fmu`. It is a standard FMI 2.0 Co-Simulation FMU and can be loaded by any FMI-compliant master or co-simulation environment.

To also generate a JSON build report:
```bash
python -m cs_fmu_packager my_system.ssp --report build-report.json
```

## Troubleshooting

### vcpkg or SUNDIALS not found
Set the `VCPKG_ROOT` environment variable:
```bash
export VCPKG_ROOT=/path/to/vcpkg
```
Or pass `--vcpkg-root /path/to/vcpkg` on the command line.

### C compiler not found
Install gcc or clang. On Ubuntu/Debian:
```bash
sudo apt install build-essential
```

### Spec validation errors
- Check that `SystemStructure.ssd` contains `<Components>` with `source` URIs that exist inside the `.ssp` archive.
- Connector `kind` must be one of: `input`, `output`, `parameter`, `calculatedParameter`, `inout`.
- Boundary connector `element` paths use the form `<component>/<variable>`.
- Solver policy (step sizes, algebraic-loop iteration) comes from the `cs-fmu-packager` vendor annotation; if present, `stepSize` must be ≤ `communicationStep`.

### The build fails
Run with `--verbose` to see detailed pipeline output:
```bash
python -m cs_fmu_packager my_system.ssp --verbose
```
This prints each pipeline phase and any warnings from the mapping step.

## Next Steps

- [README.md](README.md) — project overview, CLI reference, prerequisites
- [CONTRIBUTING.md](CONTRIBUTING.md) — developer guide and how to contribute
- [cs-fmu-packager-project/README.md](cs-fmu-packager-project/README.md) — design intent, scope, architecture motivation
- [product-breakdown/](product-breakdown/) — full product breakdown structure
- [product-breakdown/02-architecture/decisions/](product-breakdown/02-architecture/decisions/) — architecture decision records
- [product-breakdown/06-evolution/candidates/](product-breakdown/06-evolution/candidates/) — proposed improvements and feature candidates