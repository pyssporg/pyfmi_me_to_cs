# Contributing to cs-fmu-packager

## Table of Contents
1. Getting Started
2. Development Setup
3. Running Tests
4. Project Structure
5. Making Changes
6. Pull Request Process
7. Coding Conventions
8. Documentation & Decision Records
9. Questions & Support

## Getting Started
- If you are new to the project, start with GETTING_STARTED.md for a from-scratch walkthrough and README.md for an overview.
- `docs/breakdown/00-intent/purpose.md` explains design intent and scope.

## Development Setup
1. Clone the repository.
2. Create a Python virtual environment (Python >= 3.11 required):
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
3. Install in editable mode with development dependencies:
   ```bash
   pip install -e ".[dev]"
   ```
   This also installs `pyssp-standard` (FMU metadata inspection library) as a transitive dependency.
4. Verify installation:
   ```bash
   python -m cs_fmu_packager --help
   ```

## Running Tests
The project uses pytest:
```bash
pytest
```
All tests must pass before submitting changes. If you add functionality,
add corresponding tests in the `tests/` directory. CI runs the reduced gate
`pytest -m "not verification"` and then the OMC/fmpy verification file
`pytest -m verification tests/test_cs_behavior_verification.py` separately.

To run a specific test file:
```bash
pytest tests/test_ssp_spec.py -v
```

## Project Structure
A quick overview of key directories and files:

| Path | Purpose |
|------|---------|
| `src/cs_fmu_packager/` | Python package source code |
| `src/cs_fmu_packager/ssp_spec.py` | SSP package (`.ssp`) parser and normalizer |
| `src/cs_fmu_packager/cli.py` | CLI entry point (Click command) |
| `src/cs_fmu_packager/builder.py` | CMake build orchestration |
| `src/cs_fmu_packager/mapper.py` | Spec-to-FMU variable mapping |
| `src/cs_fmu_packager/codegen/` | C wrapper code generation (f-string) |
| `src/cs_fmu_packager/packager.py` | Final FMU assembly (ZIP) |
| `src/cs_fmu_packager/models.py` | Dataclass definitions |
| `docs/breakdown/` | Product breakdown structure (7 layers) |
| `src/cs_fmu_packager/c_headers/` | FMI 2.0 C headers shipped as package data |

## Making Changes

### Small fixes and documentation
Open a pull request directly. No issue required for typos, docs, or minor bug fixes.

### New features or design changes
1. Open an issue first or check the candidate proposals in `docs/breakdown/06-evolution/candidates/`.
2. Discuss the approach before implementing.
3. For changes that affect packaging behavior, solver strategy, or the spec format, update or create an architecture decision record (AD) in `docs/breakdown/02-architecture/decisions/`.

## Pull Request Process
1. Ensure all tests pass.
2. Update documentation (README, docs, ADs) if the change affects the public interface, CLI, spec format, or architecture.
3. If the change adds or modifies a user-visible feature, add or update the relevant test case.
4. If the change is a durable design decision, write a short AD entry or update the decision log.
5. Request review from a maintainer.
6. Keep PRs focused — one logical change per PR.

## Coding Conventions
- Python: target Python 3.11+. Use type hints. Follow PEP 8. Lint with `ruff check src tests`; `ruff.toml` at the repo root configures the rule set that CI enforces.
- C (generated code templates): C99. Consistent indentation (4 spaces). Avoid platform-specific idioms beyond Linux x86_64 (see AD-006).
- Tests: prefer pytest style over unittest.TestCase.
- Error messages: clear, actionable, and specific. Include the offending value and expected constraint.

## Documentation & Decision Records
- Use `docs/breakdown/` to document intent, product scope, architecture, implementation decisions, verification strategy, operation, and evolution candidates.
- Architecture decision records (AD-001 through AD-008) live in `docs/breakdown/02-architecture/decisions/`; AD-006 is under `docs/breakdown/01-product/decisions/`.
- The decision log at `docs/breakdown/decision-log.md` indexes all ADs.
- Evolution candidates in `docs/breakdown/06-evolution/candidates/` are proposals; they need a task contract before implementation begins.

## Questions & Support
Open a GitHub issue for questions, bug reports, or feature requests.