# IMP-028: Multi-FMU Composite Codegen Cannot Compile or Run (Packaged SCC Groups)

Use this template for one backlog-ready improvement candidate.

An improvement candidate is not implementation approval. It needs a scoped task contract before code or documentation changes begin.

## Lifecycle Stage

Candidate

## Status

Reported (BLOCKING) — verified 2026-09-15 from `sim_arch_comparison` PD-005 P3 (packaged SCC-group realization)

## Layer

Implementation (codegen + runtime FMU loading): `src/cs_fmu_packager/codegen/{wrapper,fmi_interface}.py`, `src/cs_fmu_packager/packager.py`

## Theme

Generated C wrapper does not compile for multi-FMU composites; and even when compiled, it cannot load the embedded internal Model Exchange FMUs at runtime.

## Context

`cs-fmu-packager` v0.1.1 packages one or more ME FMUs into a single CS FMU. The `sim_arch_comparison` Study 2 composite path packages SCC groups containing >1 ME node (OMC 1.26.1 `PassThroughNodeME` FMUs, `modelIdentifier = PassThroughNodeME_n10`, symbols prefixed `PassThroughNodeME_n10_fmi2*`). All single-FMU and trivial paths may hide these defects; they surface on any real multi-FMU group.

## Evidence

### A. Codegen cannot compile multi-FMU composites (six independent defects)

1. **Missing `fmi2_interface.h`** — `generate_all()` (codegen/wrapper.py) writes `fmi2_interface.c`, `solver_integration.c` and `fixed_point_iteration.c`, all of which `#include "fmi2_interface.h"`, but the header is never emitted (it is not in `c_headers/` nor a template). CMake fails: `fatal error: fmi2_interface.h: No such file or directory`.
2. **Python list interpolation** — `fmu_idx_defs` / `fmu_idx_assigns` are Python `list`s interpolated directly into the C template (`{fmu_idx_defs}`), emitting a Python-repr literal (`['    0 = 0;', ...]`) into `fmi2_interface.c`.
3. **`idx_*` scope escape** — aliases `int idx_<fmu> = -1;` are declared inside the loading function but used from other functions (variable/connection mapping init), e.g. `inst->connections_src[0].fmu = &inst->internal_fmus[idx_m11];` → undeclared identifier.
4. **Non-variadic `log_message`** — `static void log_message(inst, status, category, msg)` is called with printf-style extra args (`"...failed at t=%g", t`).
5. **Typo `fmu2Real`** — `fmu2Real dummy[1];` in the loading block (should be `fmi2Real`).
6. **Wrong dlsym prefix** — fallback symbol lookups use `{fmu_id}_fmi2*` (the instance alias, e.g. `m12_fmi2Instantiate`) instead of `{model_identifier}_fmi2*` (the actual exported symbol `PassThroughNodeME_n10_fmi2Instantiate`).

### B. Runtime blocker: internal ME FMUs are never extractable

Even with A fixed, the generated wrapper `dlopen`s `resources/%s/binaries/linux64/{model_identifier}.so` (per internal FMU id), but `packager.assemble_fmu()` embeds the internal ME FMUs **as zips** at `resources/{fmu_id}.fmu`. No extraction step exists anywhere in the generated wrapper or the packager, so the `.so` path never exists and `dlopen` fails at `fmi2Instantiate`. This is a design gap (see AD-004 Embedded FMU Resources), not a typo.

### C. Local patch status (in this checkout)

Implemented in this working tree (upstream-quality; closes the runtime gap):

- `codegen/fmi2_interface.h` — new static header with the FMI includes plus
  the function-pointer typedefs, `WrapperState`/`InternalFMU`/
  `VariableMapping`/`WrapperInstance` structs (now also carries `internal_vr`,
  `exitInitialize`, `sunctx`). All three `.c` units compile against it.
- `codegen/fmi_interface.py` — emits literal FMU indices (no `idx_*` aliases),
  sets `fmu->nx` from `ModelStructure/Derivatives`, drives enter/exit
  initialization, normalises `file://`/`/resources` resource-location layouts,
  passes each internal FMU its own GUID + callbacks, variadic `log_message`,
  `fmu2Real`→`fmi2Real` typo fixed, `{model_identifier}` dlsym fallbacks.
- `codegen/fixed_point.py` — `.internal_fmu` → `.fmu` member access.
- `codegen/solver.py` — SUNDIALS v7 API (`ARKode*`, `SUNContext`, explicit
  only `ARKStepCreate`), fixed-stepper.
- `codegen/wrapper.py` — `fmi2_interface.h` ships as a static template
  (copied with the other `.h`); fragile post-generation header extraction
  removed.
- `packager.py` — embeds each internal FMU's pre-extracted `binaries/` +
  `resources/` trees under `resources/{id}/` (normalised to
  `<modelIdentifier>.so`), closing the extraction gap (B).
- `model_description.py` — FMI 2.0 XSD-conformant `modelDescription.xml`
  (CoSimulation attrs, `VendorAnnotations`, legal `initial`/`start`, boundary
  value references matching the C wrapper).
- `tests/test_end_to_end.py::TestMultiFmuEndToEnd` — two-ME-node chained e2e
  test (OMC-generated integrator → gain, fmpy master).

Verified 2026-09-15: the two-node chain builds, packages, and simulates;
CSV records `y[1]`, `m00.y[1]`, `m01.y[1]`. All `tests/` pass (54 tests).

## Proposed Fix Scope (for upstream)

1. `generate_all()` must emit `fmi2_interface.h` (shared type declarations; guard with `#ifndef`) and copy the `solver_integration.h`/`fixed_point_iteration.h` templates — or stop `#include`-ing them from `.c` sources.
2. Join `fmu_idx_defs/assigns` before interpolation; prefer literal indices in mapping/connection init.
3. Drop the `idx_*` indirection (numeric indices).
4. Make `log_message` variadic (`va_list`/`vsnprintf`).
5. Fix `fmu2Real` typo.
6. Use `{model_identifier}` for all dlsym fallback prefixes.
7. **Extraction (blocking):** at wrapper init, extract each internal `resources/{id}.fmu` zip to `resources/{id}/` before `dlopen`, or embed pre-extracted `binaries/linux64/*.so` trees under `resources/{id}/`.
8. Add a multi-FMU end-to-end test (≥2 chained ME nodes; boundary vars + internal probe outputs; assert CSV records them).

## Acceptance Criteria

- A two-ME-node chained spec (`m00 -> m01`, `PassThroughNodeME`) builds a composite CS FMU; `python -m cs_fmu_packager spec.toml` exits 0 with no warnings-as-errors.
- An external master (ssp4sim v0.2.11) executes it: `sim.init(); sim.simulate()` exit 0.
- CSV records boundary variables (`u[1]/y[1]`) and node probe outputs (`m00.y[1]`, `m01.y[1]`).
- Regression: all existing `tests/` pass.

## Related Artifacts

- sim_arch_comparison: `product-breakdown/01-product/decisions/PD-005-package-scc-groups-as-composite-fmus.md`, `product-breakdown/03-implementation/study2-composite-fmu-plan.md` (P3 blocked), `docs/roadmap/study2-maturity.md` §7.