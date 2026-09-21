# Quickstart Example

A fully runnable example: a two-node Model Exchange chain packaged into a
single Co-Simulation FMU.

```
        +-----------------+      +-------------+
 u ────►│ m00: Integrator │ y ──►│ m01: Gain   │── y ───► (wrapper output)
        +-----------------+      +-------------+
```

- `m00` integrates `u` (`der(x) = gain·u`, `gain = 1.0`)
- `m01` amplifies the result (`y = k·u`, `k = 2.0`)
- Expected steady-state: a unit step on `u` yields `y ≈ 2.0`

## Prerequisites

- `omc` (OpenModelica compiler) — generate the ME FMUs
- CMake ≥ 3.20, a C compiler (gcc/clang)
- vcpkg with SUNDIALS installed, `VCPKG_ROOT` set
  (see `../../GETTING_STARTED.md` for the vcpkg setup)
- cs-fmu-packager installed (`pip install -e .` from the repo root)

## 1. Build the SSP package

```bash
python build_example.py            # writes quickstart.ssp in this directory
```

This generates `integrator.fmu` and `gain.fmu` with OMC and assembles the
complete `quickstart.ssp` archive from `SystemStructure.ssd`.

## 2. Validate (dry run)

```bash
python -m cs_fmu_packager quickstart.ssp --dry-run
```

Expected output:

```
Dry run: spec validated and FMUs inspected successfully.
  Execution order: m00 -> m01
  Algebraic loops: 0
```

## 3. Build the Co-Simulation FMU

```bash
python -m cs_fmu_packager quickstart.ssp --report build-report.json
```

Expected output:

```
Successfully created: quickstart.fmu
  2 FMU(s), 5 variable(s), 1 connection(s)
```

The count includes the three wrapper-local solver parameters
(`solver.type`, `solver.tolerance`, `solver.step_size`) — see
`../../docs/CONFIGURATION.md` for the full boundary contract.

## 4. Simulate with an external master

```bash
python - <<'EOF'
import fmpy
res = fmpy.simulate_fmu("quickstart.fmu", stop_time=1.0, start_values={"u": 1.0})
print(res)
EOF
```

The final value of `y` should be ≈ `2.0`.

## Files

| File | Purpose |
|------|---------|
| `SystemStructure.ssd` | SSP 1.0 system structure description (boundary connectors, connection, vendor solver annotation) |
| `models/Integrator.mo`, `models/Gain.mo` | Modelica sources |
| `build_example.py` | Generates the ME FMUs and assembles `quickstart.ssp` |

## Configuration

The vendor annotation in `SystemStructure.ssd` configures the wrapper:

```xml
<Solver type="fixed_step" stepSize="1e-3" tolerance="1e-6" communicationStep="1e-2" />
<AlgebraicLoop maxIterations="100" tolerance="1e-6" />
<Wrapper communicationStep="1e-2" />
```

Try changing `Solver type="variable_step"` or `type="cvode"`, then rebuild.
All options are documented in `../../docs/CONFIGURATION.md`.