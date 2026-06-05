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

### Constraints

- Linux x86_64 only
- Fixed-step execution only
- FMI 2.0 only

### Known Limitations

See `risks.md` and improvement candidates under `candidates/`.