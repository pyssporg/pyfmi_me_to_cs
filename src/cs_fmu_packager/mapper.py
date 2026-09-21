"""Mapping between package specification and FMU variables.

Validates all variable references from the spec against actual FMU variables,
detects strongly connected components (algebraic loops), and produces
the resolved MappingTable.
"""

from __future__ import annotations

from typing import Dict, List

from pyssp_standard.standard.fmi2.model.model_description import (
    Fmi2ModelDescriptionDocument,
    Fmi2ScalarVariable,
)
from pyssp_standard.standard.operations import connection_graph

from cs_fmu_packager.errors import MappingError
from cs_fmu_packager.fmu_reader import inspect_fmu
from cs_fmu_packager.models import (
    AlgebraicLoop,
    FmuRef,
    MappingTable,
    MappedVariable,
    PackageSpec,
    ResolvedConnection,
    WrapperVariable,
    build_reserved_parameters,
)


def _build_variable_lookup(
    doc: Fmi2ModelDescriptionDocument,
) -> Dict[str, Fmi2ScalarVariable]:
    """Build a name-to-variable lookup dict from a model description."""
    return {v.name: v for v in doc.variables}


def _resolve_fmu_variable(
    fmu_id: str,
    var_name: str,
    var_lookups: Dict[str, Dict[str, Fmi2ScalarVariable]],
    origin: str = "",
) -> Fmi2ScalarVariable:
    """Look up a variable in an FMU's metadata."""
    lookup = var_lookups.get(fmu_id)
    if lookup is None:
        msg = f"FMU '{fmu_id}' not found in inspected metadata"
        raise MappingError(f"{origin}: {msg}" if origin else msg)

    var = lookup.get(var_name)
    if var is None:
        msg = (
            f"Variable '{var_name}' not found in FMU '{fmu_id}' "
            f"(available: {sorted(lookup.keys())})"
        )
        raise MappingError(f"{origin}: {msg}" if origin else msg)
    return var


def _validate_connection_direction(
    conn: ResolvedConnection,
    source_var: Fmi2ScalarVariable,
    target_var: Fmi2ScalarVariable,
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


def _detect_unsupported_features(
    doc: Fmi2ModelDescriptionDocument,
) -> List[str]:
    """Detect unsupported FMU features and return warning messages."""
    unsupported: List[str] = []
    capabilities = doc.capabilities
    if capabilities and not capabilities.can_get_and_set_fmu_state:
        unsupported.append("FMU does not support get/set state")
    n_ei = doc.number_of_event_indicators or 0
    if n_ei > 0:
        unsupported.append(
            f"FMU has {n_ei} event indicators (event handling limited)"
        )
    return unsupported


def _auto_discover_variables(
    fmu_docs: Dict[str, Fmi2ModelDescriptionDocument],
) -> List[WrapperVariable]:
    """Auto-discover wrapper variables from FMU metadata (Option A: Expose all).

    Creates a WrapperVariable for every input, output, and parameter
    from all FMUs. Inputs and parameters become wrapper inputs (target),
    outputs become wrapper outputs (source).
    """
    variables: List[WrapperVariable] = []
    for fmu_id, doc in fmu_docs.items():
        for var in doc.variables:
            if var.causality == "input":
                variables.append(WrapperVariable(
                    name=var.name,
                    type=var.type_name,
                    causality="input",
                    target_fmu=fmu_id,
                    target_variable=var.name,
                    source_fmu=None,
                    source_variable=None,
                    description=var.description or "",
                ))
            elif var.causality == "output":
                variables.append(WrapperVariable(
                    name=var.name,
                    type=var.type_name,
                    causality="output",
                    source_fmu=fmu_id,
                    source_variable=var.name,
                    target_fmu=None,
                    target_variable=None,
                    description=var.description or "",
                ))
            elif var.causality == "parameter":
                variables.append(WrapperVariable(
                    name=var.name,
                    type=var.type_name,
                    causality="parameter",
                    target_fmu=fmu_id,
                    target_variable=var.name,
                    source_fmu=None,
                    source_variable=None,
                    description=var.description or "",
                ))
    return variables


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
    fmu_docs: Dict[str, Fmi2ModelDescriptionDocument] = {}
    for fmu_id, fmu_ref in spec.fmus.items():
        fmu_docs[fmu_id] = inspect_fmu(fmu_ref.path)

    # Build variable lookups
    var_lookups: Dict[str, Dict[str, Fmi2ScalarVariable]] = {}
    for fmu_id, doc in fmu_docs.items():
        var_lookups[fmu_id] = _build_variable_lookup(doc)

    # Auto-discover variables if spec has none (IMP-013, Option A)
    if not spec.variables:
        spec.variables = _auto_discover_variables(fmu_docs)

    warnings: List[str] = []

    # Resolve connections
    resolved_connections: List[ResolvedConnection] = []
    for idx, conn in enumerate(spec.connections):
        source_var = _resolve_fmu_variable(conn.source_fmu, conn.source_variable, var_lookups, origin=f"Connection {idx}")
        target_var = _resolve_fmu_variable(conn.target_fmu, conn.target_variable, var_lookups, origin=f"Connection {idx}")

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
                sv = _resolve_fmu_variable(var.target_fmu, var.target_variable, var_lookups, origin=f"Variable {idx} target")
                mapped.target_fmu = var.target_fmu
                mapped.target_variable = var.target_variable
                mapped.target_value_reference = sv.value_reference
                mapped.unit = sv.unit
                mapped.description = sv.description
            wrapper_inputs.append(mapped)

        elif var.causality == "output":
            # Outputs source from internal FMU variables
            if var.source_fmu and var.source_variable:
                sv = _resolve_fmu_variable(var.source_fmu, var.source_variable, var_lookups, origin=f"Variable {idx} source")
                mapped.source_fmu = var.source_fmu
                mapped.source_variable = var.source_variable
                mapped.source_value_reference = sv.value_reference
                mapped.unit = sv.unit
                mapped.description = sv.description
            wrapper_outputs.append(mapped)

        elif var.causality == "parameter":
            # Parameters target internal FMU variables
            if var.target_fmu and var.target_variable:
                sv = _resolve_fmu_variable(var.target_fmu, var.target_variable, var_lookups, origin=f"Variable {idx} target")
                mapped.target_fmu = var.target_fmu
                mapped.target_variable = var.target_variable
                mapped.target_value_reference = sv.value_reference
                mapped.unit = sv.unit
                mapped.description = sv.description
            wrapper_parameters.append(mapped)

    # Detect algebraic loops (strongly connected components)
    conn_pairs = [(c.source_fmu, c.target_fmu) for c in resolved_connections]
    execution_order, scc_sets = connection_graph.compute_execution_order(conn_pairs)

    algebraic_loops: List[AlgebraicLoop] = []
    for scc in scc_sets:
        scc_connections = [
            c for c in resolved_connections
            if c.source_fmu in scc and c.target_fmu in scc
        ]
        algebraic_loops.append(
            AlgebraicLoop(
                fmus=list(scc),
                connections=scc_connections,
                iterations=spec.solver.algebraic_loop.max_iterations,
                tolerance=spec.solver.algebraic_loop.tolerance,
            )
        )

    # Ensure all FMUs are in the execution order
    fmu_ids = list(spec.fmus.keys())
    all_ordered = set(execution_order)
    for fid in fmu_ids:
        if fid not in all_ordered:
            execution_order.append(fid)

    # Reserved wrapper parameters (master-visible solver knobs).  These are
    # wrapper-local: they carry no target FMU, so the C init emits fmu = NULL
    # and the generated setters route them into WrapperInstance solver fields.
    reserved_parameters = build_reserved_parameters(spec)

    # Assign deterministic wrapper boundary value references (1..N) in the
    # same order used by model_description.py (inputs, outputs, parameters,
    # reserved parameters).  The wrapper C code matches these when the master
    # calls fmi2Set*/fmi2Get*.
    for idx, mapped in enumerate(
        wrapper_inputs + wrapper_outputs + wrapper_parameters + reserved_parameters,
        1,
    ):
        mapped.wrapper_value_reference = idx

    # Collect warnings from unsupported FMU features
    for fmu_id, doc in fmu_docs.items():
        for feature in _detect_unsupported_features(doc):
            warnings.append(f"FMU '{fmu_id}': {feature}")

    return MappingTable(
        fmus=fmu_docs,
        wrapper_inputs=wrapper_inputs,
        wrapper_outputs=wrapper_outputs,
        wrapper_parameters=wrapper_parameters,
        reserved_parameters=reserved_parameters,
        connections=resolved_connections,
        algebraic_loops=algebraic_loops,
        execution_order=execution_order,
        warnings=warnings,
    )
