# Module: models

**File:** `src/cs_fmu_packager/models.py`

## Responsibility

Defines the structured representation of package specifications, parsed FMU metadata, and mapping tables used throughout the packaging pipeline. All data types are `@dataclass` classes.

## Key Dataclasses

| Class | Fields | Purpose |
| --- | --- | --- |
| `FmuRef` | name, path, fmi_version, kind | Reference to an internal Model Exchange FMU |
| `Connection` | source_fmu, source_variable, target_fmu, target_variable | Internal connection between two FMU variables |
| `WrapperVariable` | name, type, causality, source_fmu/var, target_fmu/var, start, description, unit, variability | A variable exposed at the packaged FMU boundary |
| `AlgebraicLoopConfig` | max_iterations, tolerance | Configuration for fixed-point algebraic loop handling |
| `SolverConfig` | type, step_size, communication_step, algebraic_loop | Solver configuration for the wrapper |
| `WrapperConfig` | communication_step | Wrapper-level configuration |
| `PackageSpec` | metadata, fmus, connections, variables, solver, wrapper | Complete parsed package specification |
| `ScalarVariable` | name, value_reference, type, causality, variability, description, unit, start | Metadata for a single ScalarVariable in an FMU |
| `FmuMetadata` | fmi_version, guid, model_name, variables, unsupported_features, ... | Parsed metadata from FMU modelDescription.xml |
| `MappedVariable` | wrapper_name, variable_type, causality, target/source refs, start, ... | A resolved variable mapping between wrapper and internal FMU |
| `ResolvedConnection` | source_fmu/var/vr, target_fmu/var/vr | A resolved internal connection with value references |
| `AlgebraicLoop` | fmus, connections, iterations, tolerance | Detected strongly connected component |
| `MappingTable` | fmus, wrapper_inputs/outputs/parameters, connections, algebraic_loops, execution_order, warnings | Complete resolved mapping |
| `BuildReport` | spec_path, output_path, tool_version, fmu_count, variable_count, ... | Machine-readable build report |

## Source

- `src/cs_fmu_packager/models.py` (219 lines)

## Related Tests

- Used by all test files as shared data structures