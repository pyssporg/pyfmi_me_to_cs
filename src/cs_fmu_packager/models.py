"""Data models for the cs-fmu-packager tool.

Defines the structured representation of package specifications,
parsed FMU metadata, and mapping tables used throughout the packaging pipeline.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


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
    start: Optional[float] = None
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
# FMU Metadata (from modelDescription.xml)
# ---------------------------------------------------------------------------


@dataclass
class ScalarVariable:
    """Metadata for a single ScalarVariable in an FMU."""

    name: str
    value_reference: int
    type: str  # "Real", "Integer", "Boolean", "String"
    causality: str = "local"
    variability: str = "continuous"
    description: Optional[str] = None
    unit: Optional[str] = None
    start: Optional[float] = None


@dataclass
class FmuMetadata:
    """Parsed metadata from an FMU's modelDescription.xml."""

    fmi_version: str
    guid: str
    model_name: str
    model_types: List[str] = field(default_factory=list)
    can_get_and_set_fmu_state: bool = False
    can_serialize_fmu_state: bool = False
    can_provide_directional_derivatives: bool = False
    provides_directional_derivatives: bool = False
    variables: Dict[str, ScalarVariable] = field(default_factory=dict)
    variables_by_ref: Dict[int, ScalarVariable] = field(default_factory=dict)
    continuous_states: List[str] = field(default_factory=list)
    event_indicators: List[str] = field(default_factory=list)
    unsupported_features: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Mapping Table
# ---------------------------------------------------------------------------


@dataclass
class MappedVariable:
    """A resolved variable mapping between wrapper and internal FMU."""

    wrapper_name: str
    variable_type: str  # "Real"
    causality: str  # "input", "output", "parameter"

    # For inputs/parameters: target is the FMU variable to set
    target_fmu: Optional[str] = None
    target_variable: Optional[str] = None
    target_value_reference: Optional[int] = None

    # For outputs: source is the FMU variable to get
    source_fmu: Optional[str] = None
    source_variable: Optional[str] = None
    source_value_reference: Optional[int] = None

    start: Optional[float] = None
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

    fmus: Dict[str, FmuMetadata]
    wrapper_inputs: List[MappedVariable] = field(default_factory=list)
    wrapper_outputs: List[MappedVariable] = field(default_factory=list)
    wrapper_parameters: List[MappedVariable] = field(default_factory=list)
    connections: List[ResolvedConnection] = field(default_factory=list)
    algebraic_loops: List[AlgebraicLoop] = field(default_factory=list)
    execution_order: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def all_variables(self) -> List[MappedVariable]:
        return self.wrapper_inputs + self.wrapper_outputs + self.wrapper_parameters


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