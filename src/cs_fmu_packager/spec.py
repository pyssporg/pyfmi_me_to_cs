"""Package specification parsing and validation.

Reads a TOML spec file, validates all fields, and returns a PackageSpec
dataclass. All validation errors are collected before raising.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import toml

from cs_fmu_packager.errors import SpecValidationError
from cs_fmu_packager.models import (
    AlgebraicLoopConfig,
    Connection,
    FmuRef,
    PackageSpec,
    SolverConfig,
    WrapperConfig,
    WrapperVariable,
)


def _validate_fmu_ref(fmu_id: str, data: Dict[str, Any], errors: List[str]) -> Optional[FmuRef]:
    """Validate a single FMU reference entry."""
    if not isinstance(data, dict):
        errors.append(f"fmus.{fmu_id}: must be a table")
        return None

    path = data.get("path")
    if not path:
        errors.append(f"fmus.{fmu_id}: missing required field 'path'")
        return None

    fmi_version = data.get("fmi_version", "2.0")
    if fmi_version != "2.0":
        errors.append(f"fmus.{fmu_id}.fmi_version: must be '2.0', got '{fmi_version}'")

    kind = data.get("kind", "ModelExchange")
    if kind != "ModelExchange":
        errors.append(f"fmus.{fmu_id}.kind: must be 'ModelExchange', got '{kind}'")

    return FmuRef(
        name=fmu_id,
        path=path,
        fmi_version=fmi_version,
        kind=kind,
    )


_VARIABLE_REF_RE = None  # optional compile for performance


def _parse_variable_ref(ref: str) -> Optional[tuple]:
    """Parse '<fmu_id>.<variable_name>' syntax. Returns (fmu_id, var_name) or None."""
    if "." not in ref:
        return None
    parts = ref.split(".", 1)
    if not parts[0] or not parts[1]:
        return None
    return (parts[0], parts[1])


def _validate_connection(
    idx: int, data: Dict[str, Any], fmu_keys: set, errors: List[str]
) -> Optional[Connection]:
    """Validate a single connection entry."""
    if not isinstance(data, dict):
        errors.append(f"connections[{idx}]: must be a table")
        return None

    source = data.get("source")
    target = data.get("target")

    if not source:
        errors.append(f"connections[{idx}]: missing required field 'source'")
    if not target:
        errors.append(f"connections[{idx}]: missing required field 'target'")

    if not source or not target:
        return None

    # Parse and validate source
    src_parsed = _parse_variable_ref(source)
    if not src_parsed:
        errors.append(f"connections[{idx}].source: invalid format '{source}', expected '<fmu_id>.<variable_name>'")
        return None
    if src_parsed[0] not in fmu_keys:
        errors.append(f"connections[{idx}].source: FMU '{src_parsed[0]}' not defined in [fmus]")

    # Parse and validate target
    tgt_parsed = _parse_variable_ref(target)
    if not tgt_parsed:
        errors.append(f"connections[{idx}].target: invalid format '{target}', expected '<fmu_id>.<variable_name>'")
        return None
    if tgt_parsed[0] not in fmu_keys:
        errors.append(f"connections[{idx}].target: FMU '{tgt_parsed[0]}' not defined in [fmus]")

    return Connection(
        source_fmu=src_parsed[0],
        source_variable=src_parsed[1],
        target_fmu=tgt_parsed[0],
        target_variable=tgt_parsed[1],
    )


def _validate_variable(
    idx: int,
    data: Dict[str, Any],
    fmu_keys: set,
    seen_names: set,
    errors: List[str],
) -> Optional[WrapperVariable]:
    """Validate a single wrapper variable entry."""
    if not isinstance(data, dict):
        errors.append(f"variables[{idx}]: must be a table")
        return None

    name = data.get("name")
    if not name:
        errors.append(f"variables[{idx}]: missing required field 'name'")
        return None

    if name in seen_names:
        errors.append(f"variables[{idx}].name: duplicate variable name '{name}'")
    seen_names.add(name)

    var_type = data.get("type", "Real")
    if var_type not in ("Real", "Integer", "Boolean", "String"):
        errors.append(f"variables[{idx}]: type must be 'Real', 'Integer', 'Boolean', or 'String', got '{var_type}'")

    causality = data.get("causality", "input")
    if causality not in ("input", "output", "parameter"):
        errors.append(
            f"variables[{idx}].causality: must be 'input', 'output', or 'parameter', got '{causality}'"
        )

    start = data.get("start")
    if start is not None:
        var_type = data.get("type", "Real")
        if var_type == "Real" and not isinstance(start, (int, float)):
            errors.append(f"variables[{idx}].start: must be a number for Real type")
        elif var_type == "Integer" and not isinstance(start, int):
            errors.append(f"variables[{idx}].start: must be an integer for Integer type")
        elif var_type == "Boolean" and not isinstance(start, bool):
            errors.append(f"variables[{idx}].start: must be a boolean for Boolean type")
        elif var_type == "String" and not isinstance(start, str):
            errors.append(f"variables[{idx}].start: must be a string for String type")

    source_var = data.get("source")
    target_var = data.get("target")

    # Validate source/target references
    if source_var is not None:
        src_parsed = _parse_variable_ref(source_var)
        if not src_parsed:
            errors.append(
                f"variables[{idx}].source: invalid format '{source_var}', expected '<fmu_id>.<variable_name>'"
            )
        elif src_parsed[0] not in fmu_keys:
            errors.append(
                f"variables[{idx}].source: FMU '{src_parsed[0]}' not defined in [fmus]"
            )

    if target_var is not None:
        tgt_parsed = _parse_variable_ref(target_var)
        if not tgt_parsed:
            errors.append(
                f"variables[{idx}].target: invalid format '{target_var}', expected '<fmu_id>.<variable_name>'"
            )
        elif tgt_parsed[0] not in fmu_keys:
            errors.append(
                f"variables[{idx}].target: FMU '{tgt_parsed[0]}' not defined in [fmus]"
            )

    return WrapperVariable(
        name=name,
        type=var_type,
        causality=causality,
        source_fmu=src_parsed[0] if source_var and _parse_variable_ref(source_var) else None,
        source_variable=src_parsed[1] if source_var and _parse_variable_ref(source_var) else None,
        target_fmu=tgt_parsed[0] if target_var and _parse_variable_ref(target_var) else None,
        target_variable=tgt_parsed[1] if target_var and _parse_variable_ref(target_var) else None,
        start=start,
    )


def _validate_solver(data: Dict[str, Any], errors: List[str]) -> SolverConfig:
    """Validate the [solver] section."""
    if not isinstance(data, dict):
        errors.append("solver: must be a table")
        return SolverConfig()

    solver_type = data.get("type", "fixed_step")
    if solver_type != "fixed_step":
        errors.append(f"solver.type: must be 'fixed_step' (v1 constraint), got '{solver_type}'")

    step_size = data.get("step_size", 1e-3)
    if not isinstance(step_size, (int, float)) or step_size <= 0:
        errors.append(f"solver.step_size: must be a positive number, got {step_size}")

    communication_step = data.get("communication_step", 1e-3)
    if not isinstance(communication_step, (int, float)) or communication_step <= 0:
        errors.append(
            f"solver.communication_step: must be a positive number, got {communication_step}"
        )

    if isinstance(step_size, (int, float)) and isinstance(communication_step, (int, float)):
        if step_size > communication_step:
            errors.append(
                f"solver.step_size ({step_size}) must be <= solver.communication_step ({communication_step})"
            )

    # Validate algebraic_loop section if present
    alg_loop = data.get("algebraic_loop", {})
    if not isinstance(alg_loop, dict):
        errors.append("solver.algebraic_loop: must be a table")
        alg_loop = {}

    max_iter = alg_loop.get("max_iterations", 100)
    tolerance = alg_loop.get("tolerance", 1e-6)

    if "max_iterations" in alg_loop and (not isinstance(max_iter, int) or max_iter <= 0):
        errors.append(f"solver.algebraic_loop.max_iterations: must be a positive integer, got {max_iter}")

    if "tolerance" in alg_loop and (not isinstance(tolerance, (int, float)) or tolerance <= 0):
        errors.append(f"solver.algebraic_loop.tolerance: must be a positive number, got {tolerance}")

    return SolverConfig(
        type=solver_type,
        step_size=float(step_size),
        communication_step=float(communication_step),
        algebraic_loop=AlgebraicLoopConfig(
            max_iterations=int(max_iter) if isinstance(max_iter, int) else 100,
            tolerance=float(tolerance),
        ),
    )


def _validate_wrapper(data: Dict[str, Any], errors: List[str]) -> WrapperConfig:
    """Validate the [wrapper] section."""
    if not isinstance(data, dict):
        errors.append("wrapper: must be a table")
        return WrapperConfig()

    communication_step = data.get("communication_step", 1e-3)
    if not isinstance(communication_step, (int, float)) or communication_step <= 0:
        errors.append(
            f"wrapper.communication_step: must be a positive number, got {communication_step}"
        )

    return WrapperConfig(communication_step=float(communication_step))


def parse_spec(path: str) -> PackageSpec:
    """Parse and validate a TOML package specification file.

    Args:
        path: Path to the .toml spec file.

    Returns:
        A validated PackageSpec instance.

    Raises:
        SpecValidationError: If the spec has validation errors.
    """
    if not os.path.exists(path):
        raise SpecValidationError(f"Spec file not found: {path}")

    try:
        with open(path, "r") as f:
            raw = toml.load(f)
    except Exception as e:
        raise SpecValidationError(f"Failed to parse TOML spec: {e}") from e

    errors: List[str] = []

    # Check required sections (metadata is optional)
    required_sections = ["fmus", "connections", "solver", "wrapper"]
    _required_display = {
        "fmus": "[fmus]",
        "connections": "[[connections]]",
        "solver": "[solver]",
        "wrapper": "[wrapper]",
    }
    for section in required_sections:
        if section not in raw or raw[section] is None:
            errors.append(f"Missing required section: {_required_display[section]}")

    if errors:
        raise SpecValidationError("\n".join(errors))

    # Parse metadata (optional)
    metadata = raw.get("metadata", {})

    # Parse FMU refs
    fmu_keys = set()
    fmu_refs: Dict[str, FmuRef] = {}
    if isinstance(raw.get("fmus"), dict):
        for fmu_id, fmu_data in raw["fmus"].items():
            ref = _validate_fmu_ref(fmu_id, fmu_data, errors)
            if ref is not None:
                fmu_refs[fmu_id] = ref
                fmu_keys.add(fmu_id)

    # Parse connections
    connections: List[Connection] = []
    if isinstance(raw.get("connections"), list):
        for idx, conn_data in enumerate(raw["connections"]):
            conn = _validate_connection(idx, conn_data, fmu_keys, errors)
            if conn is not None:
                connections.append(conn)

    # Parse variables
    variables: List[WrapperVariable] = []
    seen_names: set = set()
    if isinstance(raw.get("variables"), list):
        for idx, var_data in enumerate(raw["variables"]):
            var = _validate_variable(idx, var_data, fmu_keys, seen_names, errors)
            if var is not None:
                variables.append(var)

    # Parse solver
    solver = _validate_solver(raw.get("solver", {}), errors)

    # Parse wrapper
    wrapper = _validate_wrapper(raw.get("wrapper", {}), errors)

    # Check solver.communication_step vs wrapper.communication_step consistency
    if abs(solver.communication_step - wrapper.communication_step) > 1e-15:
        errors.append(
            f"solver.communication_step ({solver.communication_step}) must equal "
            f"wrapper.communication_step ({wrapper.communication_step})"
        )

    if errors:
        raise SpecValidationError("\n".join(errors))

    return PackageSpec(
        metadata=metadata if isinstance(metadata, dict) else {},
        fmus=fmu_refs,
        connections=connections,
        variables=variables,
        solver=solver,
        wrapper=wrapper,
    )