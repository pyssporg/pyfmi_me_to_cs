# AD-004: Embedded FMU Resources

**Status:** Accepted

## Context

The generated Co-Simulation FMU needs access to the internal Model Exchange FMU binaries at runtime. Two approaches were considered:

1. **Embedded resources:** Store internal FMU ZIP contents inside the generated FMU's `resources/` directory. The wrapper extracts or loads them at initialization.
2. **External references:** Store paths or references to external FMU files. The importer must ensure internal FMUs are available separately.

Embedding creates self-contained FMUs but increases size. External references reduce size but create deployment dependencies.

## Decision

Embed internal ME FMU ZIPs in **`resources/<fmu_id>.fmu`** inside the generated FMU archive. The wrapper loads them dynamically during `fmi2Instantiate` / initialization. The embedded FMUs are byte-for-byte copies of the original input FMUs.

## Consequences

- **Positive:** Self-contained FMU — no external file dependencies at runtime.
- **Positive:** Simplifies distribution and deployment.
- **Negative:** Output FMU size increases by the sum of internal FMU sizes.
- **Negative:** Internal FMU contents are inspectable by end users (may be a concern for IP protection).

## Affected Artifacts

- `src/cs_fmu_packager/packager.py` — `assemble_fmu()` embeds FMUs in `resources/`
- `src/cs_fmu_packager/codegen/fmi_interface.py` — generated C code loads from resources path