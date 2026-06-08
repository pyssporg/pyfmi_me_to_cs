# Changelog

## v0.1.0 — Initial Development Release

### Added

- Core packaging pipeline: spec parse → FMU inspect → mapping → codegen → build → package
- TOML package specification format with full validation
- C wrapper code generation for FMI 2.0 Co-Simulation interface
- SUNDIALS ARKODE fixed-step solver integration
- Fixed-point iteration for algebraic loop handling
- Deterministic FMU ZIP assembly
- Machine-readable build report
- CLI with `--dry-run`, `--verbose`, `--report` options
- Custom exception hierarchy with specific error types
- Test suite: 13 spec validation, 6 FMU inspection, 7 mapper, 4 codegen, 4 end-to-end tests
- Architecture decision records (AD-001 through AD-006)
- Product breakdown structure (this directory)

| IMP-006 | GitHub Actions CI workflow | Evolution | Completed | 2026-06-05 | `.github/workflows/test.yml` |
| IMP-011 | Test fixture improvements   | Evolution | Completed | 2026-06-05 | `tests/conftest.py`, `tests/fixtures/` |
| IMP-013 | Optional `[[variables]]` + pyssp-standard backend | Evolution | Completed | 2026-06-05 | `src/cs_fmu_packager/fmu_reader.py`, `src/cs_fmu_packager/spec.py`, `src/cs_fmu_packager/mapper.py`, `pyproject.toml`, `tests/` |
| IMP-014 | Modelica-based test fixture generation and behavioral verification | Evolution | Completed | 2026-06-08 | `tests/fixtures/modelica/`, `tests/fixtures/generate_test_fmus.py`, `tests/fixtures/cs_verification.py`, `tests/test_cs_behavior_verification.py`, `Makefile`, `pyproject.toml`, `.github/workflows/test.yml`, `product-breakdown/04-verification/test-strategy.md`, `product-breakdown/06-evolution/risks.md` |

### Constraints

- Linux x86_64 only
- Fixed-step execution only
- FMI 2.0 only

### Known Limitations

See `risks.md` and improvement candidates under `candidates/`.