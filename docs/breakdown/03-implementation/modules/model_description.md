# Module: model_description

**File:** `src/cs_fmu_packager/model_description.py`

## Responsibility

Builds the packaged Co-Simulation `modelDescription.xml` document with
`pyfmi_interfaces` and supplies the one tool-specific annotation payload.
FMI XML spelling, annotation placement, and the document model are owned by
`pyfmi_interfaces`; this module owns only the values and the
`cs-fmu-packager` payload. It does not own the FMI facade or any solver code.

## Key Functions

| Function | Description |
| --- | --- |
| `generate_model_description(spec, mapping)` | Assemble the `Fmi2ModelDescriptionDocument`, attach the `cs-fmu-packager` annotation, and serialize it |
| `_annotation_payload(spec, mapping)` | Build the `<CsFmuPackager>` fragment: solver policy, internal FMU list, algebraic-loop policy, and the `<InternalConnections>` graph |
| `_document(spec, mapping)` | Map the specification and mapping onto the shared FMI 2.0 document fields |
| `_start_value(causality, variable_type, start)` | Apply the FMI 2.0 input/parameter start rule |
| `_now_iso()` | Wall-clock `generationDateAndTime`, unchanged from the previous writer |
| `_derive_guid` | Backwards-compatible alias for `cs_fmu_packager.guid.derive_guid` |

## Ownership split

- `pyfmi_interfaces` is the one document emitter: it renders the FMI fields,
  the `CoSimulation` capability flags, `ModelVariables`,
  `ModelStructure/Outputs`, and the canonical `VendorAnnotations` wrapper.
  There is no legacy or expanded layout; formatting is the library codec's.
- `src/cs_fmu_packager/guid.py` derives the GUID from the specification
  content (MD5). `codegen/fmi_interface.py` imports that module directly.
- `src/cs_fmu_packager/model_description.py` supplies the GUID, the wall-clock
  timestamp, the wrapper variable set, and the opaque
  `<CsFmuPackager>`/`<InternalConnections>` payload under annotation name
  `cs-fmu-packager`.

## Generated Content

- FMI 2.0 Co-Simulation element with the v1 capability flags spelled
  explicitly
- One `VendorAnnotations/Tool` entry named `cs-fmu-packager` carrying solver
  type, step sizes, tolerance, internal FMU list, algebraic-loop policy, and
  the internal connection graph
- `ModelVariables` in `mapping.all_variables()` order with the stable wrapper
  value references
- `ModelStructure/Outputs` listing the wrapper outputs
- `generationTool="pyfmi_interfaces tooling"` and the content-derived GUID

## Source

- `src/cs_fmu_packager/model_description.py`
- `src/cs_fmu_packager/guid.py`

## Related Tests

- `tests/test_codegen.py` — `TestModelDescriptionCodegen`,
  `TestModelDescriptionRoundTrip`, `TestReservedSolverParameters`
