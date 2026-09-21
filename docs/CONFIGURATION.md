# Configuration Reference

This is the canonical reference for every configurable aspect of
`cs-fmu-packager`. It is authoritative over the brief notes in `README.md`,
`GETTING_STARTED.md`, and the module docs under `product-breakdown/`.

Configuration is expressed at **four levels**, in increasing precedence:

| # | Level | Where | When it applies |
|---|-------|-------|-----------------|
| 1 | Built-in defaults | hard-coded defaults (see below) | always |
| 2 | Vendor annotation | `cs-fmu-packager` `<Annotations>` block in the SSD | build time |
| 3 | CLI overrides | `--step-size`, `--communication-step` | build time |
| 4 | Runtime solver parameters | `solver.*` parameters on the packaged FMU | simulation time (master) |

Higher levels override lower ones. Levels 2–4 are all optional; level 1
always applies.

## 1. The vendor annotation

Solver and wrapper policy is carried by a vendor annotation in
`SystemStructure.ssd`. The annotation type must be `cs-fmu-packager`, and it
may contain three child elements: `Solver`, `AlgebraicLoop`, and `Wrapper`.
Any other annotation type is ignored.

```xml
<ssd:SystemStructureDescription
    xmlns:ssd="http://ssp-standard.org/SSP1/SystemStructureDescription"
    xmlns:ssc="http://ssp-standard.org/SSP1/SystemStructureCommon">
  <ssd:System name="System">
    <!-- connectors, elements, connections ... -->
  </ssd:System>
  <ssd:Annotations>
    <ssc:Annotation type="cs-fmu-packager">
      <Solver type="fixed_step" stepSize="1e-3" tolerance="1e-6" communicationStep="1e-2" />
      <AlgebraicLoop maxIterations="100" tolerance="1e-6" />
      <Wrapper communicationStep="1e-2" />
    </ssc:Annotation>
  </ssd:Annotations>
</ssd:SystemStructureDescription>
```

### 1.1 `Solver`

| Attribute | Type | Default | Meaning |
|-----------|------|---------|---------|
| `type` | string | `fixed_step` | One of the supported solver types (see [§3](#3-solver-types)) |
| `stepSize` | float > 0 | `1e-3` | Fixed integration step size; ignored by adaptive solvers |
| `tolerance` | float > 0 | `1e-6` | Integration tolerance (relative and absolute) |
| `communicationStep` | float > 0 | `1e-3` | Local communication step between wrapper and master |

### 1.2 `AlgebraicLoop`

| Attribute | Type | Default | Meaning |
|-----------|------|---------|---------|
| `maxIterations` | int > 0 | `100` | Cap on fixed-point iterations per algebraic loop |
| `tolerance` | float > 0 | `1e-6` | Convergence threshold (max connection delta) |

### 1.3 `Wrapper`

| Attribute | Type | Default | Meaning |
|-----------|------|---------|---------|
| `communicationStep` | float > 0 | `1e-3` | Communication step advertised to the master |

### 1.4 Constraints (validated)

- `stepSize` must be `≤ communicationStep`.
- `Solver.communicationStep` must equal `Wrapper.communicationStep`.
- `Solver.type` must be one of the supported solver types.
- All numeric values must be positive.

Violations raise a `SpecValidationError` with the offending value and the
expected constraint.

## 2. CLI overrides

`--step-size` and `--communication-step` override the values parsed from the
vendor annotation (and fall back to defaults when the annotation is absent).

```bash
python -m cs_fmu_packager my_system.ssp --step-size 0.5e-3 --communication-step 1e-2
```

These are a non-XML escape hatch; the vendor annotation remains the canonical
carrier and is what gets embedded in the packaged FMU's
`modelDescription.xml`.

## 3. Solver types

The packaged FMU's local solver is selected at build time by
`Solver type="..."`. The integer values below are part of the packaged FMU
contract — they are the start value of the master-visible `solver.type`
parameter and must not be renumbered.

| `type` value | Integer enum | Step control | Notes |
|--------------|--------------|--------------|-------|
| `fixed_step` | 0 | slices communication step by `stepSize` | default; explicit Euler via ARKODE |
| `variable_step` | 1 | adaptive, evolves straight to the communication point | |
| `fixed_rk2` | 2 | slices communication step by `stepSize` | fixed 2nd-order Runge–Kutta |
| `fixed_rk4` | 3 | slices communication step by `stepSize` | fixed 4th-order Runge–Kutta |
| `cvode` | 4 | adaptive, evolves straight to the communication point | CVODE ADAMS integrator (SUNDIALS) |
| `backward_euler` | 5 | slices communication step by `stepSize` | fully implicit; Newton solve with dense linear solver |

Adaptive solver types (`variable_step`, `cvode`) ignore `stepSize` and evolve
directly to the communication point; all others slice the communication step
by `stepSize`.

## 4. Runtime solver parameters (master-visible)

The packaged CS FMU exposes three **reserved** parameters that the external
master can set — via `fmi2SetReal` / `fmi2SetInteger` **before
`fmi2EnterInitializationMode`** — to select the local solver policy at
runtime. They are wrapper-local: they are not forwarded to any internal FMU.

| Parameter | FMI type | Start value | Meaning |
|-----------|----------|-------------|---------|
| `solver.type` | Integer | enum value of the build-time solver type | Solver type (see [§3](#3-solver-types)) |
| `solver.tolerance` | Real | build-time tolerance | Integration tolerance (relative and absolute) |
| `solver.step_size` | Real | build-time step size | Fixed-step integration step size |

## 5. Boundary variables

Boundary (wrapper-level) variables are declared as system-level connectors in
the SSD. The `element` attribute is a `<component>/<variable>` path.

| Connector `kind` | Wrapper causality | Notes |
|------------------|-------------------|-------|
| `input` | `input` | settable from the master |
| `output` | `output` | readable from the master |
| `parameter` | `parameter` | settable from the master |
| `calculatedParameter` | `output` | exposed as a readable output |
| `inout` | `input` | settable from the master |

Start values for boundary variables come from `<ParameterBindings>` /
`<ParameterValues>` in the SSD.

**Auto-discovery:** if no connectors are declared, every internal FMU input,
output, and parameter is automatically exposed at the boundary with its own
name (IMP-013). Declared connectors and auto-discovered variables follow the
same mapping rules.

## 6. Feature warnings (not errors)

During mapping, the following FMU capabilities produce warnings (visible with
`--verbose`) rather than errors:

- **No get/set FMU state** — the FMU does not support `fmi2GetFMUstate` /
  `fmi2SetFMUstate`; the packaged CS FMU does not advertise state save/restore.
- **Event indicators** — the FMU declares `numberOfEventIndicators > 0`;
  event handling inside the wrapper is limited.

## 7. Packaged FMU contract (modelDescription.xml)

The generated CS FMU advertises:

- **Co-Simulation capabilities:** fixed communication step size
  (`canHandleVariableCommunicationStepSize="false"`), no input interpolation,
  no FMU-state get/set or serialization, no directional derivative, and
  `numberOfEventIndicators="0"`.
- **Vendor annotations** under `<Tool name="cs-fmu-packager">`
  (`CsFmuPackager` element) recording the build-time policy:
  `solverType`, `solverStepSize`, `solverTolerance`, `communicationStepSize`,
  `internalFMUs`, `algebraicLoopCount`, `algebraicLoopMaxIterations`,
  `algebraicLoopTolerance`, and an `InternalConnections` list.
- **ModelStructure/Outputs** declaring the wrapper outputs (Unknown index =
  boundary value reference).

## 8. Defaults summary

| Setting | Default |
|---------|---------|
| Solver type | `fixed_step` |
| `step_size` | `1e-3` |
| `communication_step` | `1e-3` |
| `solver.tolerance` | `1e-6` |
| `AlgebraicLoop.max_iterations` | `100` |
| `AlgebraicLoop.tolerance` | `1e-6` |
| Wrapper `communication_step` | `1e-3` |

## 9. Related

- Runnable example: `examples/quickstart/`
- Implementation: `src/cs_fmu_packager/ssp_spec.py` (`_parse_vendor_config`),
  `src/cs_fmu_packager/models.py` (dataclasses and reserved parameters),
  `src/cs_fmu_packager/mapper.py` (auto-discovery and warnings)
- Tests: `tests/test_ssp_spec.py` (vendor config, connector kinds),
  `tests/test_mapper.py` (auto-discovery, unsupported features)