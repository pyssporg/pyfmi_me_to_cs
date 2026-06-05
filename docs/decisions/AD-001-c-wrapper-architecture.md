# AD-001: C Wrapper Architecture

**Status:** Accepted

## Context

The cs-fmu-packager generates a Co-Simulation FMU that wraps internal Model Exchange FMUs. The wrapper must instantiate internal FMUs, connect their variables, execute a local solver, and expose a Co-Simulation interface. A key architectural decision is whether the wrapper implementation should be generated as C/C++ source code (compiled to a native shared library) or use a Python runtime (e.g., via `fmpy` or PyFMI).

A Python-based approach would simplify development by leveraging existing libraries, but it would require Python to be bundled inside the FMU, which increases size, creates platform dependency issues for the Python interpreter, and makes the FMU harder to integrate into existing FMI master algorithms that expect native shared libraries.

## Decision

Generate C wrapper source code that compiles to a `.so` shared library using GCC/Clang and CMake. No Python runtime is bundled in the generated FMU.

## Consequences

- **Positive:** The generated FMU is a self-contained native shared library without runtime interpreter dependencies.
- **Positive:** Standard FMI 2.0 importers can load the FMU without special handling.
- **Positive:** C code yields better performance and smaller footprint than a Python-based wrapper.
- **Negative:** Development is more complex than using Python-level FMI libraries.
- **Negative:** Dynamic loading of internal FMU shared libraries must be implemented manually via `dlopen`.

## Affected Artifacts

- `src/cs_fmu_packager/codegen/*.py` — C source code generation
- `src/cs_fmu_packager/c_templates/*.jinja` — Jinja2 C templates
- `src/cs_fmu_packager/builder.py` — CMake + GCC build orchestration