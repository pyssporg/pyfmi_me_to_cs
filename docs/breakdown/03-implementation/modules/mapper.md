# Module: mapper

**File:** `src/cs_fmu_packager/mapper.py`

## Responsibility

Mapping between package specification and FMU variables. Validates all variable references from the spec against actual FMU variables, detects strongly connected components (algebraic loops) via pyssp_standard connection_graph, and produces the resolved `MappingTable`.

## Key Functions

| Function | Description |
| --- | --- |
| `build_mapping(spec)` | Build a resolved MappingTable from a PackageSpec |
| `_resolve_fmu_variable(fmu_id, var_name, ...)` | Look up a variable in an FMU's metadata |
| `_validate_connection_direction(...)` | Check that connection direction is compatible |
| `_build_variable_lookup(doc)` | Build a name-to-variable lookup dict from a model description |
| `_detect_unsupported_features(doc)` | Detect unsupported FMU features for warning collection |
| *(private functions removed in IMP-027)* | SCC detection and topological sort delegated to `pyssp_standard.standard.operations.connection_graph.compute_execution_order()` |

## Pipeline

1. Inspect all referenced FMUs via `fmu_reader.inspect_fmu()`
2. Resolve all connections (source/target variable lookups)
3. Validate connection directions
4. Resolve wrapper variables (inputs, outputs, parameters)
5. Detect algebraic loops via pyssp_standard connection_graph.compute_execution_order()
6. Ensure all FMUs present in execution order (fallback for loop-only nodes)

## Source

- `src/cs_fmu_packager/mapper.py` (265 lines)

## Related Tests

- `tests/test_mapper.py` — 8 tests covering basic mapping, unknown variables, parameter mapping, single FMU, algebraic loop detection, non-Real types, auto-discover variables