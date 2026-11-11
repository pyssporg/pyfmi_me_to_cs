# AGENTS

## Vision first (required)

Before you read code, edit files, or plan a change, read the project vision:

**`docs/breakdown/00-intent/intent.md`**

It states why this repository exists, what it commits to, and what it refuses to
become. It is the first document to read, not a reference of last resort.

- Read it in full before making any change to code, tests, docs, or artifacts.
- Judge every proposed change against it. If a change conflicts with the vision,
  its commitments, goals, or non-goals, stop and surface the conflict; do not
  implement it silently.
- If the work shows the long-term direction is wrong, change the vision
  deliberately first, then the code. Never let the repository drift away from
  its stated intent.

## Rules

1. **Don't assume. Surface tradeoffs.** If a contract is ambiguous, stop and say
   so rather than picking a behaviour silently.
2. **Minimum code that solves the problem.** Nothing speculative.
3. **Touch only what you must.** Clean up only your own mess.
4. **Define success criteria and verify.**

## Repository Focus

`pyfmi_me_to_cs` converts complete SSP packages (`.ssp`) — one or more FMI 2.0
Model Exchange FMUs wired together in a `SystemStructure.ssd` — into a single
FMI 2.0 Co-Simulation FMU (`.fmu`). The output CS FMU exposes a normal
Co-Simulation interface to an external master algorithm while internally
instantiating the packaged Model Exchange FMUs, connecting their variables,
advancing them with a configurable local solver, and exposing selected inputs,
outputs, parameters, and status information at the wrapper boundary.

- Current state, the full scope, and architectural motivation live in
  `docs/breakdown/`; the code is the source of truth when the two disagree.
- Dated decisions live in `docs/archive/archive.zip`, read with `pb archive`.

## Hard constraints

- **One boundary, one coupled equation system.** The packaged FMU solves all
  internal FMUs together behind a single Co-Simulation boundary; internal
  connections and algebraic loops are resolved at every integrator stage.
- **No artifact emission beyond the CS FMU.** This tool consumes SSP/SSD and
  emits one Co-Simulation FMU. It does not emit SSD, SSV, SSM, or intermediate
  files.
- **Linux x86_64 only in v1.** The build toolchain targets Linux x86_64 with
  vcpkg/SUNDIALS. Other platforms are out of scope until explicitly prioritized.
- **The solver is SUNDIALS.** IDA is the default solver; a bump is an
  architecture decision that lands with a record and verification.
- **Fixtures are evidence.** Every fixture directory has a `case.md` listing its
  files; a document of 15 or more lines is a file, never a test literal.

## Code guidelines

- Keep changes direct and explicit. Minimize duplication, but do not hide the
  SSP-to-CS conversion logic behind abstractions.
- Public entry points take their policy keyword-only and required; private
  helpers take it positionally and forward it. No default domain.
- Keep error messages naming the member, its owner, and the path involved.
- Treat interfaces as pre-1.0: clarity outranks compatibility shims.

## Conventions

- `README.md` is the landing page; `docs/breakdown/` holds current state.
- `docs/breakdown/` follows the product-breakdown skill. Set
  `PB=<skills-dir>/product-breakdown/scripts/pb` and pass
  `--root docs/breakdown` to every command:
  - current state lives in layer leaves, in the present tense;
  - dated decisions live in `docs/archive/archive.zip` (`pb archive list`,
    `pb archive read <ID>`, `pb archive add <FILE>`);
  - never add per-layer `decisions/` folders or hand-maintain decision logs;
  - regenerate `docs/archive/README.md`, `design-choice-log.md`, and
    `traceability-map.md` with `python3 $PB registers --root docs/breakdown`;
    never edit them by hand;
  - run `python3 $PB check --strict --root docs/breakdown` and
    `python3 $PB node-size --strict --root docs/breakdown` after edits.
- Version lives in `src/cs_fmu_packager/__init__.py` only; `pyproject.toml` is
  dynamic and has no `[project].version`.

## Environment

- Python >= 3.10; CI runs 3.11 and 3.12.
- CMake >= 3.20, C compiler (gcc/clang), vcpkg with SUNDIALS.
- `python3 -m venv venv`, `source venv/bin/activate`,
  `pip install -e ".[dev]"`.
- Tests: `python3 -m pytest -m "not slow"` (the CI gate); a bare
  `python3 -m pytest` includes the slow set.
- Lint: `ruff check src tests`.
- Build: `python -m build --wheel --sdist`.