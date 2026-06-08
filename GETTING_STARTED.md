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

### Step 1: Create a spec file

Create a file called `my_system.toml`:

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

Replace `"path/to/compressor.fmu"` and `"path/to/valve.fmu"` with the actual paths to your FMI 2.0 Model Exchange FMU files.

For a fully commented example, see `spec.example.toml` (if available in the repository root; see [IMP-002](product-breakdown/06-evolution/candidates/IMP-002.md)).

### Step 2: Validate your spec (dry run)

```bash
python -m cs_fmu_packager my_system.toml --dry-run
```

This validates the spec and inspects your FMU files without building anything. You should see output like:

```
Dry run: spec validated and FMUs inspected successfully.
  Execution order: compressor -> valve
  Algebraic loops: 0
```

If you see errors, check the spec for typos and verify the FMU paths.

### Step 3: Build the Co-Simulation FMU

```bash
python -m cs_fmu_packager my_system.toml
```

The tool will:
1. Parse and validate your spec
2. Inspect each FMU's modelDescription.xml
3. Map wrapper variables to internal FMU variables
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
python -m cs_fmu_packager my_system.toml --report build-report.json
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
- Check that required sections are present: `[fmus]`, `[[connections]]`, `[solver]`, `[wrapper]`. The `[[variables]]` section is optional.
- Use `"fixed_step"` (not `"fixed-step"`) for `solver.type`.
- Ensure `solver.communication_step` equals `wrapper.communication_step`.
- FMU paths should be absolute or relative to the working directory.

### The build fails
Run with `--verbose` to see detailed pipeline output:
```bash
python -m cs_fmu_packager my_system.toml --verbose
```
This prints each pipeline phase and any warnings from the mapping step.

## Next Steps

- [README.md](README.md) — project overview, CLI reference, prerequisites
- [CONTRIBUTING.md](CONTRIBUTING.md) — developer guide and how to contribute
- [cs-fmu-packager-project/README.md](cs-fmu-packager-project/README.md) — design intent, scope, architecture motivation
- [product-breakdown/](product-breakdown/) — full product breakdown structure
- [product-breakdown/02-architecture/decisions/](product-breakdown/02-architecture/decisions/) — architecture decision records
- [product-breakdown/06-evolution/candidates/](product-breakdown/06-evolution/candidates/) — proposed improvements and feature candidates