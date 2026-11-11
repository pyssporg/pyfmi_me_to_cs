# Test Strategy

## Overall Approach

Three-tier testing strategy:

1. **Unit tests** — Test individual pipeline phases in isolation using synthetic FMU files (generated ZIP archives with known content).
2. **Integration tests** — Test the full packaging pipeline end-to-end, including FMU assembly and deterministic output verification.
3. **Build tests** — Test CMake build execution (conditional on `VCPKG_ROOT` being set, as they require vcpkg + SUNDIALS).

## Test Layout

| File | Type | Tests | Coverage |
| --- | --- | --- | --- |
| `test_ssp_spec.py` | Unit | 38 | SSP package parsing, normalization, validation rules, vendor config, value coercion |
| `test_fmu_inspection.py` | Unit | 12 | FMU ZIP parsing, XML extraction, validation, FMI-version rejection |
| `test_mapper.py` | Unit | 17 | Variable resolution, connection direction, SCC detection, auto-discovery, warnings |
| `test_codegen.py` | Unit | 28 | CMake generation, model description, C interface golden file, valueReference invariants, solver knobs |
| `test_builder.py` | Unit | 13 | vcpkg/CMake build integration and error paths |
| `test_packager.py` | Unit | 13 | FMU assembly error paths, inner-FMU runtime payload embedding, build report |
| `test_end_to_end.py` | Integration | 22 | Assembly, build report, deterministic output, CLI pipeline, multi-FMU runtime |
| `test_cs_behavior_verification.py` | Behavioral | 4 | Trajectory comparison framework against OMC reference FMUs |

Total: 147 tests. The heavy multi-FMU integration tests are gated on
`VCPKG_ROOT`, `omc`, and `fmpy` via `@pytest.mark.skipif`; the behavioral
verification tests additionally use the `verification` marker.

## Key Design Decisions

- Tests avoid proprietary FMI tools — test FMUs are generated as in-memory ZIP files with minimal valid XML.
- Build tests are conditional (`@pytest.mark.skipif`) on `VCPKG_ROOT` being set to avoid CI failures on non-Linux or non-vcpkg environments.
- SSP package tests build complete `.ssp` archives (SSD + embedded FMUs) into temporary files, then parse them through the standard API (INP-029).
- Mapper tests create temporary FMU files via `tempfile.mkstemp` and clean up via `shutil.rmtree`.
- The multi-FMU integration tests stage OMC-generated FMUs from a module-scoped fixture (generated once per run) and package the `.ssp` through the real CLI.
- The runtime algebraic-loop and two-stateful-FMU integration tests exercise the generated C solver/fixed-point code behaviourally, not just via string assertions.

## Modelica-based Fixture Generation and Behavioral Verification

### Motivation

The original fixture generation (`generate_test_fmus.py`) hand-crafted `modelDescription.xml` via ElementTree string interpolation. This approach was:
- **Fragile** — every new test FMU required manual XML with correct FMI 2.0 schema elements, variable references, and dependency declarations.
- **Non-behavioral** — the hand-crafted XML described structure but never validated equation-system correctness.
- **Non-composable** — testing interconnected systems required manually managing metadata consistency across multiple FMUs.

The project's core ME→CS conversion pipeline had no automated behavioral validation: the test suite verified structural and metadata correctness but could not catch semantic errors in the generated solver, variable mapping, or FMU assembly.

### Two-tier approach

**Tier 1 — Modelica-based ME FMU fixture generation:**
- Modelica source files (`.mo`) live in `tests/fixtures/modelica/`.
- `generate_test_fmus.py` is rewritten to call the OpenModelica compiler (`omc`) via `subprocess`, producing FMI 2.0 Model Exchange FMUs.
- A `Makefile` target (`make generate-fixtures`) enables one-command regeneration.
- Existing tests that consume fixture FMUs (`fmu_fixture_path` in `conftest.py`) continue to work unchanged.

**Tier 2 — Dual-export behavioral verification:**
- Compound Modelica models (e.g., `IntegratorWithGain`) are exported as **both** ME and CS FMUs via OMC.
- The project's `cs-fmu-packager` converts the ME FMU into a second CS FMU (the artifact under test).
- `fmpy.simulate_fmu()` runs both CS FMUs with identical parameters.
- Output trajectories are compared using `numpy.allclose(rtol=1e-4, atol=1e-6)`.
- The comparison is implemented in `tests/fixtures/cs_verification.py` (the `verify_cs_behavior()` helper).
- Four tests in `tests/test_cs_behavior_verification.py` exercise the verification loop: (1) fixture generation sanity, (2) nominal match against an identical FMU, (3) tight-tolerance boundary, (4) input-signal sensitivity (different inputs produce detectably different trajectories).

### When to regenerate fixtures

- After changing any `.mo` file in `tests/fixtures/modelica/`.
- After upgrading the OMC version (regenerate and verify no behavioral regression).
- Before running the behavioral verification tests if fixture FMUs are stale.

### How to add new test models

1. Write a Modelica `.mo` file in `tests/fixtures/modelica/`.
2. Add an entry to the `_MODELS` dictionary in `generate_test_fmus.py`.
3. Run `make generate-fixtures`.
4. If the model is a compound system, it will automatically be included in CS export (when `--cs` is used).

### Dependencies

| Dependency | Purpose | Installation |
| --- | --- | --- |
| `omc` (OpenModelica compiler) | Compile `.mo` → FMU (ME and CS) | `apt install omc` (Ubuntu), `brew install openmodelica` (macOS) |
| `fmpy>=0.3` | Pure-Python FMI 2.0 CS runtime for simulation comparison | `pip install fmpy` (included in `[test]` optional-deps) |
| `numpy` | Array comparison via `allclose` | Transitive dependency of `fmpy` |
| `pandas` | Trajectory data structure | Transitive dependency of `fmpy` |

The verification tests are protected by `@pytest.mark.verification` and are skipped if either `omc` or `fmpy` are not installed.