"""Mapping between package specification and FMU variables.

Validates all variable references from the spec against actual FMU variables,
detects strongly connected components (algebraic loops), and produces
the resolved MappingTable.
"""

from __future__ import annotations

from typing import Dict, List, Set, Tuple

from cs_fmu_packager.errors import MappingError
from cs_fmu_packager.fmu_reader import inspect_fmu
from cs_fmu_packager.models import (
    AlgebraicLoop,
    AlgebraicLoopConfig,
    Connection,
    FmuMetadata,
    FmuRef,
    MappingTable,
    MappedVariable,
    PackageSpec,
    ResolvedConnection,
    ScalarVariable,
    WrapperVariable,
)


def _resolve_fmu_variable(
    fmu_id: str,
    var_name: str,
    fmu_metadatas: Dict[str, FmuMetadata],
    origin: str = "",
) -> ScalarVariable:
    """Look up a variable in an FMU's metadata."""
    metadata = fmu_metadatas.get(fmu_id)
    if metadata is None:
        msg = f"FMU '{fmu_id}' not found in inspected metadata"
        raise MappingError(f"{origin}: {msg}" if origin else msg)

    var = metadata.variables.get(var_name)
    if var is None:
        msg = (
            f"Variable '{var_name}' not found in FMU '{fmu_id}' "
            f"(available: {sorted(metadata.variables.keys())})"
        )
        raise MappingError(f"{origin}: {msg}" if origin else msg)
    return var


def _validate_connection_direction(
    conn: ResolvedConnection,
    source_meta: FmuMetadata,
    target_meta: FmuMetadata,
    source_var: ScalarVariable,
    target_var: ScalarVariable,
    warnings: List[str],
) -> None:
    """Check that connection direction is compatible."""
    # The source FMU variable should be an output or a local/calculable variable
    if source_var.causality == "input":
        warnings.append(
            f"Connection {conn.source_fmu}.{conn.source_variable} -> "
            f"{conn.target_fmu}.{conn.target_variable}: "
            f"source variable has causality='{source_var.causality}' "
            f"(expected 'output' or 'local')"
        )

    # The target FMU variable should be an input
    if target_var.causality not in ("input",):
        warnings.append(
            f"Connection {conn.source_fmu}.{conn.source_variable} -> "
            f"{conn.target_fmu}.{conn.target_variable}: "
            f"target variable has causality='{target_var.causality}' "
            f"(expected 'input')"
        )


def _build_adjacency_list(
    connections: List[ResolvedConnection],
    fmu_ids: List[str],
) -> Dict[str, Set[str]]:
    """Build directed adjacency graph of FMU dependencies."""
    adj: Dict[str, Set[str]] = {fmu_id: set() for fmu_id in fmu_ids}
    for conn in connections:
        if conn.source_fmu != conn.target_fmu:
            adj[conn.source_fmu].add(conn.target_fmu)
    return adj


def _tarjan_scc(
    adj: Dict[str, Set[str]],
) -> List[List[str]]:
    """Find strongly connected components using Tarjan's algorithm.

    Returns a list of SCCs, each as a list of node IDs.
    Single nodes with no self-loop are NOT returned as SCCs.
    """
    index_counter = 0
    stack: List[str] = []
    lowlink: Dict[str, int] = {}
    index: Dict[str, int] = {}
    on_stack: Dict[str, bool] = {}
    result: List[List[str]] = []

    def strongconnect(v: str) -> None:
        nonlocal index_counter
        index[v] = index_counter
        lowlink[v] = index_counter
        index_counter += 1
        stack.append(v)
        on_stack[v] = True

        for w in adj.get(v, set()):
            if w not in index:
                strongconnect(w)
                lowlink[v] = min(lowlink[v], lowlink[w])
            elif on_stack.get(w, False):
                lowlink[v] = min(lowlink[v], index[w])

        if lowlink[v] == index[v]:
            scc: List[str] = []
            while True:
                w = stack.pop()
                on_stack[w] = False
                scc.append(w)
                if w == v:
                    break
            if len(scc) > 1 or (len(scc) == 1 and v in adj.get(v, set())):
                result.append(scc)

    for node in adj:
        if node not in index:
            strongconnect(node)

    return result


def _topological_sort(
    adj: Dict[str, Set[str]],
    sccs: List[List[str]],
) -> List[str]:
    """Topologically sort FMU execution order respecting SCC grouping."""
    # Contract SCCs into single nodes
    scc_map: Dict[str, int] = {}
    for i, scc in enumerate(sccs):
        for node in scc:
            scc_map[node] = i

    # Build contracted graph
    scc_adj: Dict[int, Set[int]] = {i: set() for i in range(len(sccs))}
    for src, targets in adj.items():
        src_scc = scc_map.get(src, -1)
        if src_scc == -1:
            scc_map[src] = len(sccs)
            scc_adj[len(sccs)] = set()
            sccs.append([src])
            src_scc = scc_map[src]
        for tgt in targets:
            tgt_scc = scc_map.get(tgt, -1)
            if tgt_scc == -1:
                scc_map[tgt] = len(sccs)
                scc_adj[len(sccs)] = set()
                sccs.append([tgt])
                tgt_scc = scc_map[tgt]
            if src_scc != tgt_scc:
                scc_adj[src_scc].add(tgt_scc)

    # Kahn's algorithm
    in_degree = {i: 0 for i in range(len(sccs))}
    for src, targets in scc_adj.items():
        for tgt in targets:
            in_degree[tgt] = in_degree.get(tgt, 0) + 1

    queue = [i for i in range(len(sccs)) if in_degree[i] == 0]
    order = []
    while queue:
        node = queue.pop(0)
        order.append(node)
        for neighbor in scc_adj[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    # Flatten: within each SCC, preserve original order from scc entry
    flattened: List[str] = []
    for scc_idx in order:
        flattened.extend(sccs[scc_idx])

    return flattened


def build_mapping(spec: PackageSpec) -> MappingTable:
    """Build a resolved MappingTable from a PackageSpec.

    Inspects all referenced FMUs, validates variable references,
    detects algebraic loops, and produces the final mapping.

    Args:
        spec: Validated PackageSpec.

    Returns:
        Resolved MappingTable.

    Raises:
        MappingError: If mapping validation fails.
    """
    # Inspect all FMUs
    fmu_metadatas: Dict[str, FmuMetadata] = {}
    for fmu_id, fmu_ref in spec.fmus.items():
        fmu_metadatas[fmu_id] = inspect_fmu(fmu_ref.path)

    warnings: List[str] = []

    # Resolve connections
    resolved_connections: List[ResolvedConnection] = []
    for idx, conn in enumerate(spec.connections):
        source_var = _resolve_fmu_variable(conn.source_fmu, conn.source_variable, fmu_metadatas, origin=f"Connection {idx}")
        target_var = _resolve_fmu_variable(conn.target_fmu, conn.target_variable, fmu_metadatas, origin=f"Connection {idx}")

        resolved = ResolvedConnection(
            source_fmu=conn.source_fmu,
            source_variable=conn.source_variable,
            source_value_reference=source_var.value_reference,
            target_fmu=conn.target_fmu,
            target_variable=conn.target_variable,
            target_value_reference=target_var.value_reference,
        )

        _validate_connection_direction(
            resolved,
            fmu_metadatas[conn.source_fmu],
            fmu_metadatas[conn.target_fmu],
            source_var,
            target_var,
            warnings,
        )

        resolved_connections.append(resolved)

    # Resolve wrapper variables
    wrapper_inputs: List[MappedVariable] = []
    wrapper_outputs: List[MappedVariable] = []
    wrapper_parameters: List[MappedVariable] = []

    for idx, var in enumerate(spec.variables):
        mapped = MappedVariable(
            wrapper_name=var.name,
            variable_type=var.type,
            causality=var.causality,
            start=var.start,
        )

        if var.causality == "input":
            # Inputs target internal FMU variables
            if var.target_fmu and var.target_variable:
                sv = _resolve_fmu_variable(var.target_fmu, var.target_variable, fmu_metadatas, origin=f"Variable {idx} target")
                mapped.target_fmu = var.target_fmu
                mapped.target_variable = var.target_variable
                mapped.target_value_reference = sv.value_reference
                mapped.unit = sv.unit
                mapped.description = sv.description
            wrapper_inputs.append(mapped)

        elif var.causality == "output":
            # Outputs source from internal FMU variables
            if var.source_fmu and var.source_variable:
                sv = _resolve_fmu_variable(var.source_fmu, var.source_variable, fmu_metadatas, origin=f"Variable {idx} source")
                mapped.source_fmu = var.source_fmu
                mapped.source_variable = var.source_variable
                mapped.source_value_reference = sv.value_reference
                mapped.unit = sv.unit
                mapped.description = sv.description
            wrapper_outputs.append(mapped)

        elif var.causality == "parameter":
            # Parameters target internal FMU variables
            if var.target_fmu and var.target_variable:
                sv = _resolve_fmu_variable(var.target_fmu, var.target_variable, fmu_metadatas, origin=f"Variable {idx} target")
                mapped.target_fmu = var.target_fmu
                mapped.target_variable = var.target_variable
                mapped.target_value_reference = sv.value_reference
                mapped.unit = sv.unit
                mapped.description = sv.description
            wrapper_parameters.append(mapped)

    # Detect algebraic loops (strongly connected components)
    fmu_ids = list(spec.fmus.keys())
    adj = _build_adjacency_list(resolved_connections, fmu_ids)
    sccs = _tarjan_scc(adj)

    algebraic_loops: List[AlgebraicLoop] = []
    for scc in sccs:
        scc_connections = [
            c for c in resolved_connections
            if c.source_fmu in scc and c.target_fmu in scc
        ]
        algebraic_loops.append(
            AlgebraicLoop(
                fmus=scc,
                connections=scc_connections,
                iterations=spec.solver.algebraic_loop.max_iterations,
                tolerance=spec.solver.algebraic_loop.tolerance,
            )
        )

    # Compute execution order respecting SCCs
    execution_order = _topological_sort(adj, [scc[:] for scc in sccs])
    # Ensure all FMUs are in the order
    all_ordered = set(execution_order)
    for fid in fmu_ids:
        if fid not in all_ordered:
            execution_order.append(fid)

    # Collect warnings from unsupported FMU features
    for fmu_id, meta in fmu_metadatas.items():
        for feature in meta.unsupported_features:
            warnings.append(f"FMU '{fmu_id}': {feature}")

    return MappingTable(
        fmus=fmu_metadatas,
        wrapper_inputs=wrapper_inputs,
        wrapper_outputs=wrapper_outputs,
        wrapper_parameters=wrapper_parameters,
        connections=resolved_connections,
        algebraic_loops=algebraic_loops,
        execution_order=execution_order,
        warnings=warnings,
    )