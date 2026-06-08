"""FMU assembly and packaging.

Assembles the final FMU ZIP archive with deterministic properties
(sorted entries, fixed timestamps, no absolute paths).
"""

from __future__ import annotations

import hashlib
import json
import os
import zipfile
from datetime import datetime
from typing import Dict, List, Optional

from cs_fmu_packager.errors import PackagingError
from cs_fmu_packager.model_description import generate_model_description
from cs_fmu_packager.models import BuildReport, MappingTable, PackageSpec


# Fixed timestamp for deterministic ZIP entries (Jan 1 2020 00:00:00)
_FIXED_ZIP_TIME = (2020, 1, 1, 0, 0, 0)


def _make_zip_info(name: str) -> zipfile.ZipInfo:
    """Create a ZipInfo with deterministic properties."""
    info = zipfile.ZipInfo(name)
    info.date_time = _FIXED_ZIP_TIME
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16  # Regular file, rw-r--r--
    return info


def _compute_checksum(path: str) -> str:
    """Compute SHA-256 checksum of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def assemble_fmu(
    spec: PackageSpec,
    mapping: MappingTable,
    so_path: str,
    output_path: str,
    fmu_name: Optional[str] = None,
    build_metadata: Optional[dict] = None,
) -> BuildReport:
    """Assemble the final FMU ZIP archive.

    Args:
        spec: The package specification.
        mapping: The resolved mapping table.
        so_path: Path to the compiled .so shared library.
        output_path: Path for the output .fmu file.
        fmu_name: Optional override for the FMU identifier.
        build_metadata: Optional build metadata dict (tool versions, etc.).

    Returns:
        BuildReport with build summary.

    Raises:
        PackagingError: If FMU assembly fails.
    """
    if not fmu_name:
        fmu_name = spec.metadata.get("identifier", "cs_fmu")

    # Validate inputs
    if not os.path.exists(so_path):
        raise PackagingError(f"Compiled .so not found at: {so_path}")

    for fmu_id, fmu_ref in spec.fmus.items():
        if not os.path.exists(fmu_ref.path):
            raise PackagingError(
                f"Internal FMU '{fmu_id}' not found at: {fmu_ref.path}"
            )

    try:
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # 1. Write modelDescription.xml
            model_desc = generate_model_description(spec, mapping)
            info = _make_zip_info("modelDescription.xml")
            zf.writestr(info, model_desc.encode("utf-8"))

            # 2. Write compiled .so to binaries/linux64/
            so_target = f"binaries/linux64/{fmu_name}.so"
            info = _make_zip_info(so_target)
            with open(so_path, "rb") as f:
                zf.writestr(info, f.read())

            # 3. Embed internal ME FMUs in resources/
            for fmu_id, fmu_ref in spec.fmus.items():
                resource_target = f"resources/{fmu_id}.fmu"
                info = _make_zip_info(resource_target)
                with open(fmu_ref.path, "rb") as f:
                    zf.writestr(info, f.read())

    except (OSError, zipfile.BadZipFile) as e:
        raise PackagingError(f"Failed to create FMU archive: {e}") from e

    # Build the report
    fmu_guids: Dict[str, str] = {}
    for fmu_id, meta in mapping.fmus.items():
        fmu_guids[fmu_id] = meta.guid

    warnings = list(mapping.warnings)
    if build_metadata:
        tool_versions = build_metadata.get("tool_versions", {})
    else:
        tool_versions = {}

    return BuildReport(
        spec_path="",
        output_path=output_path,
        tool_version=tool_versions.get("python", "unknown"),
        fmu_count=len(spec.fmus),
        variable_count=len(mapping.all_variables()),
        connection_count=len(mapping.connections),
        algebraic_loop_count=len(mapping.algebraic_loops),
        solver_type=spec.solver.type,
        solver_step_size=spec.solver.step_size,
        communication_step=spec.wrapper.communication_step,
        warnings=warnings,
        fmu_guids=fmu_guids,
        wrapper_variables=[v.wrapper_name for v in mapping.all_variables()],
    )


def write_build_report(report: BuildReport, report_path: str) -> None:
    """Write a machine-readable build report as JSON.

    Args:
        report: The build report to serialize.
        report_path: Output path for the JSON report.
    """
    data = {
        "tool_version": report.tool_version,
        "fmu_count": report.fmu_count,
        "variable_count": report.variable_count,
        "connection_count": report.connection_count,
        "algebraic_loop_count": report.algebraic_loop_count,
        "solver_type": report.solver_type,
        "solver_step_size": report.solver_step_size,
        "communication_step": report.communication_step,
        "warnings": report.warnings,
        "fmu_guids": report.fmu_guids,
        "wrapper_variables": report.wrapper_variables,
    }

    try:
        with open(report_path, "w") as f:
            json.dump(data, f, indent=2)
    except OSError as e:
        raise PackagingError(f"Failed to write build report: {e}") from e