"""FMU assembly and packaging.

Assembles the final FMU ZIP archive with deterministic properties
(sorted entries, fixed timestamps, no absolute paths).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import zipfile
from datetime import datetime
from typing import Dict, List, Optional

from pyssp_standard.fmu import FMU

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


def _model_identifier_for(mapping: MappingTable, fmu_id: str) -> Optional[str]:
    """Return the model identifier of an internal FMU from the mapping."""
    fmu_doc = mapping.fmus.get(fmu_id)
    caps = fmu_doc.capabilities if fmu_doc else None
    if caps is not None and getattr(caps, "model_identifier", None):
        return caps.model_identifier
    return None


def _compute_checksum(path: str) -> str:
    """Compute SHA-256 checksum of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _inner_model_identifier(path: str) -> Optional[str]:
    """Return the ``modelIdentifier`` of an internal ME FMU.

    The generated wrapper dlopens ``resources/<id>/binaries/linux64/
    <model_identifier>.so``, so the packager must embed the internal shared
    library under exactly that name (IMP-028).
    """
    try:
        with zipfile.ZipFile(path) as zf:
            xml = zf.read("modelDescription.xml").decode("utf-8", "replace")
    except (zipfile.BadZipFile, KeyError):
        return None
    match = re.search(r'modelIdentifier\s*=\s*"([^"]+)"', xml)
    return match.group(1) if match else None


def _iter_inner_fmu_runtime_files(path: str, model_identifier: Optional[str] = None):
    """Yield ``(archive_name, bytes)`` for the runtime payload of an
    internal ME FMU (its ``binaries/`` and ``resources/`` subtrees).

    The generated wrapper ``dlopen``s the internal FMU shared library at
    ``resources/<fmu_id>/binaries/linux64/<model_identifier>.so`` (IMP-028),
    so the packaged outer FMU must ship those trees pre-extracted.  The
    shared library inside ``binaries/linux64/`` is normalised to the inner
    FMU's ``modelIdentifier`` so the dlopen path always resolves.
    """
    mi = model_identifier or _inner_model_identifier(path)
    try:
        with zipfile.ZipFile(path) as zf:
            for name in zf.namelist():
                if name.startswith("binaries/") or name.startswith("resources/"):
                    if (
                        mi
                        and name.startswith("binaries/linux64/")
                        and name.endswith(".so")
                    ):
                        renames = f"binaries/linux64/{mi}.so"
                        yield renames, zf.read(name)
                    else:
                        yield name, zf.read(name)
    except zipfile.BadZipFile as e:
        raise PackagingError(
            f"Internal FMU '{path}' is not a valid ZIP archive: {e}"
        ) from e


def _assemble_fmu_via_pyssp(
    spec: PackageSpec,
    mapping: MappingTable,
    so_path: str,
    output_path: str,
    fmu_name: str,
    date_time: datetime,
) -> None:
    """Assemble FMU using pyssp_standard's FMU.create() pathway.

    Used when ``date_time`` is provided to allow non-deterministic timestamps
    via FMU.set_generation_date_and_time().

    Args:
        spec: The package specification.
        mapping: The resolved mapping table.
        so_path: Path to the compiled .so shared library.
        output_path: Path for the output .fmu file.
        fmu_name: The FMU identifier (without extension).
        date_time: Generation date and time to set on the FMU.
    """
    # Generate modelDescription.xml
    model_desc_str = generate_model_description(spec, mapping)

    # Write modelDescription.xml to a temp file for FMU.create
    tmp_xml_fd, tmp_xml_path = tempfile.mkstemp(suffix=".xml")
    try:
        with os.fdopen(tmp_xml_fd, "w") as f:
            f.write(model_desc_str)

        # The .so must be named {fmu_name}.so for correct placement
        tmp_so_dir = tempfile.mkdtemp()
        try:
            corrected_so = os.path.join(tmp_so_dir, f"{fmu_name}.so")
            shutil.copy2(so_path, corrected_so)

            # Create the FMU archive with model description and binary
            FMU.create(
                output_path,
                model_description=tmp_xml_path,
                binaries={"linux64": corrected_so},
            )

            # Open in append mode to add resources and set generation date/time
            with FMU(output_path, mode="a") as fmu:
                tmp_inner_dir = tempfile.mkdtemp()
                try:
                    for fmu_id, fmu_ref in spec.fmus.items():
                        fmu.add_resource(
                            fmu_ref.path, target_name=f"{fmu_id}.fmu"
                        )
                        # IMP-028: embed pre-extracted runtime payload
                        # (binaries/, resources/) for dlopen at wrapper init.
                        for (inner_name, inner_bytes) in _iter_inner_fmu_runtime_files(
                            fmu_ref.path,
                            model_identifier=_model_identifier_for(mapping, fmu_id),
                        ):
                            tmp_path = os.path.join(
                                tmp_inner_dir,
                                f"{fmu_id}_{inner_name.replace('/', '_')}",
                            )
                            with open(tmp_path, "wb") as f:
                                f.write(inner_bytes)
                            fmu.add_resource(
                                tmp_path,
                                target_name=f"{fmu_id}/{inner_name}",
                            )
                            os.unlink(tmp_path)
                finally:
                    shutil.rmtree(tmp_inner_dir, ignore_errors=True)
                fmu.set_generation_date_and_time(date_time)
        finally:
            shutil.rmtree(tmp_so_dir, ignore_errors=True)
    finally:
        os.unlink(tmp_xml_path)


def assemble_fmu(
    spec: PackageSpec,
    mapping: MappingTable,
    so_path: str,
    output_path: str,
    fmu_name: Optional[str] = None,
    build_metadata: Optional[dict] = None,
    date_time: Optional[datetime] = None,
) -> BuildReport:
    """Assemble the final FMU ZIP archive.

    Args:
        spec: The package specification.
        mapping: The resolved mapping table.
        so_path: Path to the compiled .so shared library.
        output_path: Path for the output .fmu file.
        fmu_name: Optional override for the FMU identifier.
        build_metadata: Optional build metadata dict (tool versions, etc.).
        date_time: Optional generation date and time. When provided, uses
            pyssp_standard's FMU.create() pathway instead of the deterministic
            ZIP approach. Prepares for deterministic timestamp support in the
            next release.

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

    if date_time is not None:
        # Use pyssp_standard FMU.create pathway with non-deterministic timestamps
        _assemble_fmu_via_pyssp(
            spec, mapping, so_path, output_path, fmu_name, date_time,
        )
    else:
        # Use deterministic-timestamp ZIP pathway (existing behavior)
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

                    # IMP-028: also embed the pre-extracted runtime payload
                    # (binaries/, resources/) so the generated wrapper can
                    # dlopen each internal FMU without a zip-extraction step.
                    for (inner_name, inner_bytes) in _iter_inner_fmu_runtime_files(
                        fmu_ref.path,
                        model_identifier=_model_identifier_for(mapping, fmu_id),
                    ):
                        target = f"resources/{fmu_id}/{inner_name}"
                        info = _make_zip_info(target)
                        zf.writestr(info, inner_bytes)

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
