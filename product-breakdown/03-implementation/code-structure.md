# Code Structure

## Repository Layout

```
pyfmi_me_to_cs/
├── cs-fmu-packager-project/       # Project documentation
│   ├── README.md                  # Overview, intent, scope, users
│   ├── requirements.md            # All requirements (FR, SR, IR, SPR, NFR, CR, VR, C, OD)
│   └── use-cases.md              # Use cases (UC-001 through UC-006)
├── docs/
│   └── decisions/                 # Architecture decision records (original)
│       ├── AD-001-c-wrapper-architecture.md
│       ├── AD-002-sundials-solver.md
│       ├── AD-003-fixed-point-iteration.md
│       ├── AD-004-embedded-fmu-resources.md
│       ├── AD-005-toml-spec-format.md
│       └── AD-006-linux-x86-64-v1.md
├── src/
│   └── cs_fmu_packager/           # Main Python package
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli.py                 # CLI entry point (click-based)
│       ├── spec.py                # TOML spec parsing and validation
│       ├── models.py              # Data models (dataclasses)
│       ├── fmu_reader.py          # FMU inspection and XML parsing
│       ├── mapper.py              # Variable mapping and SCC detection
│       ├── model_description.py   # modelDescription.xml generation
│       ├── builder.py             # CMake build integration
│       ├── packager.py            # FMU ZIP assembly
│       ├── errors.py              # Custom exception hierarchy
│       └── codegen/               # C source code generation
│           ├── __init__.py
│           ├── wrapper.py         # Codegen orchestrator
│           ├── cmake.py           # CMakeLists.txt generation
│           ├── fmi_interface.py   # fmi2_interface.c generation
│           ├── solver.py          # solver_integration.c generation
│           └── fixed_point.py     # fixed_point_iteration.c generation
├── tests/                         # Test suite
│   ├── __init__.py
│   ├── test_spec_validation.py    # 13 tests
│   ├── test_fmu_inspection.py     # 6 tests
│   ├── test_mapper.py             # 7 tests
│   ├── test_codegen.py            # 3 test classes
│   └── test_end_to_end.py        # 4 tests
├── c_headers/                     # FMI 2.0 standard C headers
├── product-breakdown/             # This PBS directory
├── pyproject.toml                 # Python package metadata
├── CMakePresets.json              # CMake build presets
├── vcpkg.json                     # vcpkg dependency manifest
└── README.md                      # Project README
```

## Module Structure

The Python package is organized as a flat module tree with a `codegen/` sub-package:

- **Entry point**: `cli.py` (via `__main__.py` and `pyproject.toml` script)
- **Data models**: `models.py` (used by all other modules)
- **Pipeline modules**: `spec.py`, `fmu_reader.py`, `mapper.py`, `codegen/` (sub-package), `builder.py`, `packager.py`
- **Support**: `errors.py`, `model_description.py`

## Test Layout

Tests are organized by pipeline phase:
- `test_spec_validation.py` — spec parsing and validation (Phase 1)
- `test_fmu_inspection.py` — FMU inspection (Phase 2)
- `test_mapper.py` — mapping pipeline (Phase 3)
- `test_codegen.py` — C code and model description generation (Phase 4)
- `test_end_to_end.py` — assembly and full pipeline (Phase 6)