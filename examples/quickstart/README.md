# Quickstart example

Generate two Model Exchange FMUs from Modelica, package them into
`quickstart.ssp`, and convert that package into one FMI 2.0 Co-Simulation FMU.

## Run

From the workspace root, in the workspace venv:

```bash
python repos/pyfmi_me_to_cs/examples/quickstart/build_example.py
```

That is the whole example: it builds `integrator.fmu` and `gain.fmu` with
`omc`, packages both with `SystemStructure.ssd` into `quickstart.ssp`, then
runs `python -m cs_fmu_packager` for `quickstart.fmu`. Everything lands under
the gitignored `build/examples/quickstart/`:

| Path | What |
| --- | --- |
| `build/examples/quickstart/integrator.fmu` | `m00` Model Exchange FMU |
| `build/examples/quickstart/gain.fmu` | `m01` Model Exchange FMU |
| `build/examples/quickstart/quickstart.ssp` | SSP package with both FMUs |
| `build/examples/quickstart/quickstart.fmu` | Co-Simulation wrapper FMU |

Expected output:

```text
build/examples/quickstart/integrator.fmu
build/examples/quickstart/gain.fmu
build/examples/quickstart/quickstart.ssp
build/examples/quickstart/quickstart.fmu
```

Pass `--out DIR` to write elsewhere.

## Setup

Needs `omc` (OpenModelica), `cmake`, a C compiler, and vcpkg with SUNDIALS
installed (`VCPKG_ROOT` set; see `../../GETTING_STARTED.md`). Then the
workspace venv plus the one editable it does not list:

```bash
python -m venv .venv-experimental
source .venv-experimental/bin/activate
pip install --no-deps -r requirements-experimental.txt
pip install -r requirements-thirdparty.txt
pip install --no-deps -e repos/pyfmi_me_to_cs
```

## Composition

`SystemStructure.ssd` composes two units and exposes the boundary connectors
`u` and `y`:

- `m00` integrates `u` (`der(x) = gain·u`, `gain = 1.0`);
- `m01` amplifies the result (`y = k·u`, `k = 2.0`), and its output is `y`;
- the `cs-fmu-packager` annotation selects the solver and communication step
  used by the wrapper.

The units are `models/Integrator.mo` and `models/Gain.mo`; the SSD is example
input and is packaged unchanged.
