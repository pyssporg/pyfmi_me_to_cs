# Module: model_description

**File:** `src/cs_fmu_packager/model_description.py`

## Responsibility

Generates a valid FMI 2.0 Co-Simulation `modelDescription.xml` with proper capability flags, wrapper variable declarations, internal FMU annotations, and solver policy metadata.

## Key Functions

| Function | Description |
| --- | --- |
| `generate_model_description(spec, mapping)` | Generate modelDescription.xml string |
| `_derive_guid(spec)` | Derive a deterministic GUID from spec content via MD5 |
| `_now_iso()` | Generate ISO timestamp for generation date |
| `_vr_for_index(index)` | Generate a deterministic value reference for a wrapper variable |

## Generated Content

- FMI 2.0 Co-Simulation element with capability flags set for v1 (no variable step, no interpolation, no state)
- Annotations section with `CsFmuPackager` metadata (solver type, step sizes, internal FMU list, algebraic loop config)
- ModelVariables section with all wrapper boundary variables
- ModelStructure section with outputs listing
- InternalConnections annotation documenting the connection graph

## Source

- `src/cs_fmu_packager/model_description.py` (190 lines)

## Related Tests

- `tests/test_codegen.py` — `TestModelDescriptionCodegen` class (4 tests)