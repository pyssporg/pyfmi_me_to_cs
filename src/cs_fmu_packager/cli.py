"""CLI entry point for cs-fmu-packager.

Usage:
    cs-fmu-packager [OPTIONS] SPEC

See --help for full option details.
"""

from __future__ import annotations

import importlib.resources as resources
import os
import sys
import tempfile
from typing import Optional

import click

from cs_fmu_packager.builder import build_fmu
from cs_fmu_packager.codegen.wrapper import generate_all
from cs_fmu_packager.errors import (
    BuildError,
    CodegenError,
    CsFmuPackagerError,
    FmuInspectionError,
    MappingError,
    PackagingError,
    SpecValidationError,
)
from cs_fmu_packager.mapper import build_mapping
from cs_fmu_packager.packager import assemble_fmu, write_build_report
from cs_fmu_packager.ssp_spec import parse_spec


def _resolve_c_headers_dir(custom_path: Optional[str]) -> str:
    """Resolve the c_headers directory containing FMI 2.0 standard headers.

    Resolution order:
    1. Explicit --c-headers CLI option (if provided).
    2. importlib.resources lookup from installed package data.
    3. Heuristic fallback for development/source-tree usage.
    4. BuildError with actionable instructions if none resolve.
    """
    # Priority 1: explicit CLI override
    if custom_path is not None:
        resolved = os.path.abspath(custom_path)
        if not os.path.isdir(resolved):
            raise BuildError(
                f"Cannot find c-headers directory: '{custom_path}' does not exist "
                f"or is not a directory. Provide a valid path containing FMI 2.0 "
                f"header files (fmi2Functions.h, fmi2FunctionTypes.h, fmi2TypesPlatform.h)."
            )
        return resolved

    # Priority 2: importlib.resources (works for installed packages)
    try:
        headers_path = resources.files("cs_fmu_packager").joinpath("c_headers")
        if headers_path.is_dir():
            return str(headers_path)
    except (TypeError, ModuleNotFoundError, OSError):
        pass

    # Priority 3: heuristic fallback for development usage
    candidates = [
        os.path.join(os.path.dirname(__file__), "c_headers"),
        os.path.join(os.getcwd(), "c_headers"),
    ]
    for path in candidates:
        resolved = os.path.abspath(path)
        if os.path.isdir(resolved):
            return resolved

    # Terminal failure: nothing worked
    raise BuildError(
        "Cannot locate FMI 2.0 C headers directory.\n"
        "  Expected directory: c_headers (containing fmi2Functions.h, "
        "fmi2FunctionTypes.h, fmi2TypesPlatform.h)\n"
        "  The headers should be installed as package data. Try:\n"
        "    pip install .\n"
        "  Or specify the path explicitly:\n"
        "    cs-fmu-packager --c-headers /path/to/c_headers ..."
    )


@click.command(name="cs-fmu-packager")
@click.argument("spec", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "-o", "--output",
    type=click.Path(dir_okay=False),
    default=None,
    help="Output FMU path (default: <spec_basename>.fmu)",
)
@click.option(
    "-r", "--report",
    type=click.Path(dir_okay=False),
    default=None,
    help="Build report output path (JSON)",
)
@click.option(
    "--vcpkg-root",
    type=click.Path(exists=True, file_okay=False),
    default=None,
    help="Path to vcpkg installation",
)
@click.option(
    "--c-headers",
    type=click.Path(exists=False, file_okay=False),
    default=None,
    help="Path to directory containing FMI 2.0 C headers (default: auto-detect from package data)",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Validate spec + inspect FMUs only (no build)",
)
@click.option(
    "--step-size",
    type=float,
    default=None,
    help="Override the fixed-step size parsed from the SSP vendor annotation",
)
@click.option(
    "--communication-step",
    type=float,
    default=None,
    help="Override the communication step parsed from the SSP vendor annotation",
)
@click.option(
    "-v", "--verbose",
    is_flag=True,
    default=False,
    help="Enable diagnostic logging",
)
def main(
    spec: str,
    output: Optional[str],
    report: Optional[str],
    vcpkg_root: Optional[str],
    c_headers: Optional[str],
    dry_run: bool,
    step_size: Optional[float],
    communication_step: Optional[float],
    verbose: bool,
) -> None:
    """Package one or more FMI 2.0 Model Exchange FMUs into a Co-Simulation FMU.

    SPEC is the path to a complete SSP package (``.ssp``) that embeds its
    internal FMUs alongside a ``SystemStructure.ssd`` description document.
    """
    try:
        _execute(
            spec, output, report, vcpkg_root, c_headers,
            dry_run, step_size, communication_step, verbose,
        )
    except CsFmuPackagerError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


def _execute(
    spec_path: str,
    output_path: Optional[str],
    report_path: Optional[str],
    vcpkg_root: Optional[str],
    c_headers: Optional[str],
    dry_run: bool,
    step_size: Optional[float],
    communication_step: Optional[float],
    verbose: bool,
) -> None:
    """Internal execution pipeline."""
    # Resolve default output path
    if not output_path:
        base = os.path.splitext(os.path.basename(spec_path))[0]
        output_path = f"{base}.fmu"

    # Phase 1: Parse and validate the complete SSP package. Embedded FMUs are
    # extracted into a build-owned workspace that lives for the whole pipeline.
    if verbose:
        click.echo(f"Parsing SSP package: {spec_path}")

    with tempfile.TemporaryDirectory(prefix="cs_fmu_ssp_") as ssp_workspace:
        spec = parse_spec(spec_path, workspace_dir=ssp_workspace)

        # CLI overrides (escape hatch on top of the vendor annotation).
        if step_size is not None:
            if step_size <= 0:
                raise SpecValidationError(
                    f"--step-size: must be a positive number, got {step_size}"
                )
            spec.solver.step_size = float(step_size)
        if communication_step is not None:
            if communication_step <= 0:
                raise SpecValidationError(
                    f"--communication-step: must be a positive number, "
                    f"got {communication_step}"
                )
            spec.solver.communication_step = float(communication_step)
            spec.wrapper.communication_step = float(communication_step)
        if spec.solver.step_size > spec.solver.communication_step:
            raise SpecValidationError(
                f"solver.step_size ({spec.solver.step_size}) must be <= "
                f"solver.communication_step ({spec.solver.communication_step})"
            )

        if verbose:
            click.echo(
                f"  FMUs: {len(spec.fmus)}, "
                f"Connections: {len(spec.connections)}, "
                f"Variables: {len(spec.variables)}"
            )

        # Phase 2+3: Map spec to FMUs
        if verbose:
            click.echo("Inspecting FMUs and building mapping...")
        mapping = build_mapping(spec)

        if verbose:
            click.echo(
                f"  Inspected {len(mapping.fmus)} FMU(s), "
                f"resolved {len(mapping.connections)} connection(s), "
                f"found {len(mapping.algebraic_loops)} algebraic loop(s)"
            )
            for w in mapping.warnings:
                click.echo(f"  Warning: {w}")

        if dry_run:
            click.echo("Dry run: spec validated and FMUs inspected successfully.")
            click.echo(f"  Execution order: {' -> '.join(mapping.execution_order)}")
            click.echo(f"  Algebraic loops: {len(mapping.algebraic_loops)}")
            return

        # Phase 4: Code generation
        if verbose:
            click.echo("Generating C wrapper code...")

        with tempfile.TemporaryDirectory(prefix="cs_fmu_build_") as build_dir:
            try:
                resolved_headers_dir = _resolve_c_headers_dir(c_headers)
                gen_result = generate_all(spec, mapping, build_dir, resolved_headers_dir)
            except CodegenError as e:
                raise CodegenError(f"Code generation failed: {e}") from e

            if verbose:
                click.echo(f"  Generated {len(gen_result)} file(s) in {build_dir}")

            # Phase 5: Build
            if verbose:
                click.echo("Building wrapper shared library...")

            try:
                build_result = build_fmu(
                    source_dir=build_dir,
                    build_dir=os.path.join(build_dir, "_build"),
                    vcpkg_root_arg=vcpkg_root,
                    fmu_name=spec.metadata.get("identifier", "cs_fmu"),
                    verbose=verbose,
                )
            except BuildError as e:
                raise BuildError(f"Build failed: {e}") from e

            if verbose:
                click.echo(f"  Built: {build_result.so_path}")
                if build_result.arch:
                    click.echo(f"  Architecture: {build_result.arch}")

            # Phase 6: Package
            if verbose:
                click.echo(f"Assembling FMU: {output_path}")

            # Ensure output directory exists
            output_dir = os.path.dirname(os.path.abspath(output_path))
            os.makedirs(output_dir, exist_ok=True)

            try:
                report_data = assemble_fmu(
                    spec=spec,
                    mapping=mapping,
                    so_path=build_result.so_path,
                    output_path=output_path,
                    fmu_name=spec.metadata.get("identifier", "cs_fmu"),
                    build_metadata={"tool_versions": build_result.tool_versions},
                )
            except PackagingError as e:
                raise PackagingError(f"FMU assembly failed: {e}") from e

            # Write build report if requested
            if report_path:
                report_dir = os.path.dirname(os.path.abspath(report_path))
                if report_dir:
                    os.makedirs(report_dir, exist_ok=True)
                write_build_report(report_data, report_path)
                if verbose:
                    click.echo(f"  Report written: {report_path}")

            click.echo(f"Successfully created: {output_path}")
            click.echo(
                f"  {len(spec.fmus)} FMU(s), "
                f"{len(mapping.all_variables())} variable(s), "
                f"{len(mapping.connections)} connection(s)"
            )


if __name__ == "__main__":
    main()