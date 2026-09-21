"""Data models for the cs-fmu-packager tool.

Defines the structured representation of package specifications,
parsed FMU metadata, and mapping tables used throughout the packaging pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from pyssp_standard.standard.fmi2.model.model_description import Fmi2ModelDescriptionDocument


# ---------------------------------------------------------------------------
# Package Specification Models
# ---------------------------------------------------------------------------


@dataclass
class FmuRef:
    """Reference to an internal Model Exchange FMU."""

    name: str
    path: str
    fmi_version: str = "2.0"
    kind: str = "ModelExchange"


@dataclass
class Connection:
    """Internal connection between two FMU variables."""

    source_fmu: str
    source_variable: str
    target_fmu: str
    target_variable: str


@dataclass
class WrapperVariable:
    """A variable exposed at the packaged FMU boundary."""

    name: str
    type: str = "Real"
    causality: str = "input"
    source_fmu: Optional[str] = None
    source_variable: Optional[str] = None
    target_fmu: Optional[str] = None
    target_variable: Optional[str] = None
    start: Optional[float | int | bool | str] = None
    description: Optional[str] = None
    unit: Optional[str] = None
    variability: Optional[str] = None


@dataclass
class AlgebraicLoopConfig:
    """Configuration for fixed-point algebraic loop handling."""

    max_iterations: int = 100
    tolerance: float = 1e-6


@dataclass
class SolverConfig:
    """Solver configuration for the wrapper."""

    type: str = "fixed_step"
    step_size: float = 1e-3
    communication_step: float = 1e-3
    tolerance: float = 1e-6
    algebraic_loop: AlgebraicLoopConfig = field(default_factory=AlgebraicLoopConfig)


@dataclass
class WrapperConfig:
    """Wrapper-level configuration."""

    communication_step: float = 1e-3


@dataclass
class PackageSpec:
    """Complete parsed package specification."""

    metadata: Dict[str, Any] = field(default_factory=dict)
    fmus: Dict[str, FmuRef] = field(default_factory=dict)
    connections: List[Connection] = field(default_factory=list)
    variables: List[WrapperVariable] = field(default_factory=list)
    solver: SolverConfig = field(default_factory=SolverConfig)
    wrapper: WrapperConfig = field(default_factory=WrapperConfig)


# ---------------------------------------------------------------------------
# FMU Metadata (from modelDescription.xml) — delegated to pyssp_standard
# ---------------------------------------------------------------------------
# FmuMetadata and ScalarVariable have been removed.
# Use Fmi2ModelDescriptionDocument and Fmi2ScalarVariable from
# pyssp_standard.standard.fmi2.model.model_description instead.
# See fmu_reader.inspect_fmu() which now returns Fmi2ModelDescriptionDocument.

# ---------------------------------------------------------------------------
# Reserved wrapper parameters (master-visible solver knobs)
# ---------------------------------------------------------------------------
# These parameters are exposed at the packaged FMU boundary with causality
# "parameter" and are consumed by the wrapper itself (not forwarded to any
# internal FMU). A master sets them via fmi2SetReal/fmi2SetInteger before
# fmi2EnterInitializationMode to select the local solver policy at runtime.

SOLVER_TYPE_PARAM = "solver.type"
SOLVER_TOLERANCE_PARAM = "solver.tolerance"
SOLVER_STEP_SIZE_PARAM = "solver.step_size"

# Solver type names -> integer enum stored in WrapperInstance.solver_type.
# The integer values are part of the packaged FMU contract (they are the
# start value of the master-visible solver.type parameter), so they must not
# be renumbered.
SOLVER_TYPE_ENUM = {
    "fixed_step": 0,
    "variable_step": 1,
    "fixed_rk2": 2,
    "fixed_rk4": 3,
    "cvode": 4,
    "backward_euler": 5,
}

# Solver types that use adaptive step control (the generated do-step loop
# evolves straight to the communication point); all others slice the
# communication step by solver.step_size.
ADAPTIVE_SOLVER_TYPES = frozenset({"variable_step", "cvode"})

_SOLVER_TYPE_HELP = ", ".join(
    f"{idx}={name}" for name, idx in SOLVER_TYPE_ENUM.items()
)


def build_reserved_parameters(spec: PackageSpec) -> List["MappedVariable"]:
    """Build the reserved (wrapper-local) solver control parameters."""
    return [
        MappedVariable(
            wrapper_name=SOLVER_TYPE_PARAM,
            variable_type="Integer",
            causality="parameter",
            start=SOLVER_TYPE_ENUM.get(spec.solver.type, 0),
            description=f"Solver type: {_SOLVER_TYPE_HELP}",
        ),
        MappedVariable(
            wrapper_name=SOLVER_TOLERANCE_PARAM,
            variable_type="Real",
            causality="parameter",
            start=spec.solver.tolerance,
            description="Integration tolerance (relative and absolute)",
        ),
        MappedVariable(
            wrapper_name=SOLVER_STEP_SIZE_PARAM,
            variable_type="Real",
            causality="parameter",
            start=spec.solver.step_size,
            description="Fixed-step integration step size",
        ),
    ]


# ---------------------------------------------------------------------------
# Mapping Table
# ---------------------------------------------------------------------------


@dataclass
class MappedVariable:
    """A resolved variable mapping between wrapper and internal FMU."""

    wrapper_name: str
    variable_type: str  # "Real", "Integer", "Boolean", "String"
    causality: str  # "input", "output", "parameter"

    # Value reference exposed at the wrapper boundary (modelDescription.xml).
    # Assigned deterministically (1..N across all wrapper variables).
    wrapper_value_reference: Optional[int] = None

    # For inputs/parameters: target is the FMU variable to set
    target_fmu: Optional[str] = None
    target_variable: Optional[str] = None
    target_value_reference: Optional[int] = None

    # For outputs: source is the FMU variable to get
    source_fmu: Optional[str] = None
    source_variable: Optional[str] = None
    source_value_reference: Optional[int] = None

    start: Optional[float | int | bool | str] = None
    description: Optional[str] = None
    unit: Optional[str] = None


@dataclass
class ResolvedConnection:
    """A resolved internal connection between FMU variables."""

    source_fmu: str
    source_variable: str
    source_value_reference: int
    target_fmu: str
    target_variable: str
    target_value_reference: int


@dataclass
class AlgebraicLoop:
    """Detected strongly connected component (algebraic loop)."""

    fmus: List[str]
    connections: List[ResolvedConnection]
    iterations: int = 100
    tolerance: float = 1e-6


@dataclass
class MappingTable:
    """Complete resolved mapping for the packaging pipeline."""

    fmus: Dict[str, Fmi2ModelDescriptionDocument]
    wrapper_inputs: List[MappedVariable] = field(default_factory=list)
    wrapper_outputs: List[MappedVariable] = field(default_factory=list)
    wrapper_parameters: List[MappedVariable] = field(default_factory=list)
    reserved_parameters: List[MappedVariable] = field(default_factory=list)
    connections: List[ResolvedConnection] = field(default_factory=list)
    algebraic_loops: List[AlgebraicLoop] = field(default_factory=list)
    execution_order: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def all_variables(self) -> List[MappedVariable]:
        return (
            self.wrapper_inputs
            + self.wrapper_outputs
            + self.wrapper_parameters
            + self.reserved_parameters
        )


# ---------------------------------------------------------------------------
# Build Report
# ---------------------------------------------------------------------------


@dataclass
class BuildReport:
    """Machine-readable build report."""

    spec_path: str
    output_path: str
    tool_version: str
    fmu_count: int
    variable_count: int
    connection_count: int
    algebraic_loop_count: int
    solver_type: str
    solver_step_size: float
    communication_step: float
    warnings: List[str] = field(default_factory=list)
    fmu_guids: Dict[str, str] = field(default_factory=dict)
    wrapper_variables: List[str] = field(default_factory=list)