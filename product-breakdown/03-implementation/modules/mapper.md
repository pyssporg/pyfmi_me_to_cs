# Module: mapper

**File:** `src/cs_fmu_packager/mapper.py`

## Responsibility

Mapping between package specification and FMU variables. Validates all variable references from the spec against actual FMU variables, detects strongly connected components (algebraic loops) using Tarjan's algorithm, and produces the resolved `MappingTable`.

## Key Functions

| Function | Description |
| --- | --- |
| `build_mapping(spec)` | Build a resolved MappingTable from a PackageSpec |
| `_resolve_fmu_variable(fmu_id, var_name, ...)` | Look up a variable in an FMU's metadata |
| `_validate_connection_direction(...)` | Check that connection direction is compatible |
| `_build_adjacency_list(connections, ...)` | Build directed adjacency graph of FMU dependencies |
| `_tarjan_scc(adj)` | Find strongly connected components using Tarjan's algorithm |
| `_topological_sort(adj, sccs)` | Topologically sort FMU execution order respecting SCC grouping |

## Pipeline

1. Inspect all referenced FMUs via `fmu_reader.inspect_fmu()`
2. Resolve all connections (source/target variable lookups)
3. Validate connection directions
4. Resolve wrapper variables (inputs, outputs, parameters)
5. Detect algebraic loops via Tarjan's SCC algorithm
6. Compute execution order via topological sort

## Source

- `src/cs_fmu_packager/mapper.py` (326 lines)

## Related Tests

- `tests/test_mapper.py` — 7 tests covering basic mapping, unknown variables, parameter mapping, single FMU, algebraic loop detection, non-Real types