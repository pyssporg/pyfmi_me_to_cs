"""Deterministic GUID derivation for the packaged Co-Simulation FMU.

The GUID is package identity, not XML policy: it is derived from the spec
content, so it stays stable while the document writer changes. The FMI facade
and the model-description writer both read it here.
"""

from __future__ import annotations

import hashlib

from cs_fmu_packager.models import PackageSpec


def derive_guid(spec: PackageSpec) -> str:
    """Derive a deterministic GUID from spec content.

    Two specs that differ in the boundary variable set or the internal
    connections must produce different GUIDs, so the fingerprint covers
    variable names/causalities/types/targets and connection endpoints in
    addition to the solver/wrapper policy.
    """
    def _var_fingerprint(v) -> str:
        return (
            f"{v.name}:{v.causality}:{v.type}:"
            f"{v.target_fmu}.{v.target_variable}:"
            f"{v.source_fmu}.{v.source_variable}:{v.start}"
        )

    variable_fingerprint = "|".join(sorted(_var_fingerprint(v) for v in spec.variables))
    connection_fingerprint = "|".join(
        sorted(
            f"{c.source_fmu}.{c.source_variable}->{c.target_fmu}.{c.target_variable}"
            for c in spec.connections
        )
    )
    content = (
        str(sorted(spec.fmus.keys()))
        + str(spec.solver.type)
        + str(spec.solver.step_size)
        + str(spec.solver.tolerance)
        + str(spec.wrapper.communication_step)
        + variable_fingerprint
        + connection_fingerprint
    )
    h = hashlib.md5(content.encode())
    raw = h.digest()

    def _to_hex(b: bytes) -> str:
        return "".join(f"{c:02x}" for c in b)

    return (
        f"{_to_hex(raw[:4])}-{_to_hex(raw[4:6])}-"
        f"{_to_hex(raw[6:8])}-{_to_hex(raw[8:10])}-"
        f"{_to_hex(raw[10:16])}"
    )
