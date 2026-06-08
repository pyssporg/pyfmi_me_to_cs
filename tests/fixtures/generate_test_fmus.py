#!/usr/bin/env python3
"""Generate test FMU fixtures using the OpenModelica compiler (OMC).

Creates FMI 2.0 Model Exchange FMUs from Modelica source files
located in ``tests/fixtures/modelica/``.  Optionally exports
Co-Simulation FMUs for compound models (used by the behavioral
verification tests).

Requires ``omc`` (the OpenModelica compiler) to be installed.
If OMC is not found, all FMU generation is skipped with a warning.

Usage::

    python tests/fixtures/generate_test_fmus.py [output_dir]
    python tests/fixtures/generate_test_fmus.py [output_dir] --cs
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from typing import Optional

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_HERE = os.path.abspath(os.path.dirname(__file__))
_MODELICA_DIR = os.path.join(_HERE, "modelica")

# ---------------------------------------------------------------------------
# Model registry:  fixture_name -> model_info
# ---------------------------------------------------------------------------
# Each entry maps a fixture name to a tuple of:
#   (model_source_stem, is_compound, [dependency_stems])
_ModelInfo = tuple[str, bool, list[str]]

_MODELS: dict[str, _ModelInfo] = {
    "integrator": ("Integrator", False, []),
    "gain": ("Gain", False, []),
    "IntegratorWithGain": ("IntegratorWithGain", True, ["Integrator", "Gain"]),
}

# Compound models that support CS export
_COMPOUND_NAMES = {name for name, (_, compound, _) in _MODELS.items() if compound}


# ---------------------------------------------------------------------------
# OMC discovery
# ---------------------------------------------------------------------------
def find_omc() -> Optional[str]:
    """Return the path to ``omc``, or *None* if not found on ``PATH``."""
    return shutil.which("omc")


# ---------------------------------------------------------------------------
# MOS script generation
# ---------------------------------------------------------------------------
def write_mos_script(
    model_name: str,
    mo_path: str,
    dependency_mo_paths: list[str] | None = None,
    fmi_type: str = "me",
    output_prefix: str | None = None,
) -> str:
    """Write a temporary ``.mos`` script and return its path.

    The script:
    1. Loads the Modelica Standard Library
    2. Loads the given ``.mo`` file (and any dependency ``.mo`` files)
    3. Translates the model to an FMU of *fmi_type* (``"me"`` or ``"cs"``)
       using OMC's ``buildModelFMU`` built-in

    OMC places the output ``<prefix>.fmu`` in the **current working
    directory** at invocation time.

    Args:
        model_name: The Modelica class name (e.g. ``"Integrator"``).
        mo_path: Path to the primary ``.mo`` file.
        dependency_mo_paths: Additional ``.mo`` files to load first
            (for compound models that reference other classes).
        fmi_type: ``"me"`` for Model Exchange, ``"cs"`` for Co-Simulation.
        output_prefix: Custom output name (without ``.fmu``).  If *None*,
            defaults to *model_name*.
    """
    lines = ['loadModel(Modelica);']
    lines.append(f'loadFile("{mo_path}");')
    for dep_path in (dependency_mo_paths or []):
        lines.append(f'loadFile("{dep_path}");')

    prefix = output_prefix or model_name

    if fmi_type == "cs":
        lines.append(
            f'buildModelFMU({model_name}, version="2.0", fmuType="cs", '
            f'fileNamePrefix="{prefix}");'
        )
    else:
        # Default (omitted fmuType) is ME for most OMC versions
        lines.append(
            f'buildModelFMU({model_name}, version="2.0", fmuType="me", '
            f'fileNamePrefix="{prefix}");'
        )
    lines.append('getErrorString();')

    content = '\n'.join(lines) + '\n'
    fd, path = tempfile.mkstemp(suffix=".mos", prefix=f"{model_name}_")
    with os.fdopen(fd, "w") as f:
        f.write(content)
    return path


# ---------------------------------------------------------------------------
# Single FMU generation
# ---------------------------------------------------------------------------
def generate_fmu(
    model_name: str,
    mo_path: str,
    output_dir: str,
    dependency_mo_paths: list[str] | None = None,
    fmi_type: str = "me",
    output_prefix: str | None = None,
    omc_path: str = "omc",
) -> str:
    """Run OMC to produce an FMU, then move it to *output_dir*.

    Returns the final path of the FMU.
    """
    prefix = output_prefix or model_name

    mos_script = write_mos_script(
        model_name=model_name,
        mo_path=mo_path,
        dependency_mo_paths=dependency_mo_paths,
        fmi_type=fmi_type,
        output_prefix=prefix,
    )

    # OMC writes <prefix>.fmu to the CWD -- run from a temp directory
    with tempfile.TemporaryDirectory() as work_dir:
        local_mos = os.path.join(work_dir, os.path.basename(mos_script))
        shutil.copy2(mos_script, local_mos)

        try:
            result = subprocess.run(
                [omc_path, local_mos],
                cwd=work_dir,
                check=True,
                capture_output=True,
                text=True,
                timeout=120,
            )
        except subprocess.CalledProcessError as exc:
            print(f"  [ERROR] OMC failed for {model_name} ({fmi_type}):")
            print(f"    stdout: {exc.stdout[-500:]}")
            print(f"    stderr: {exc.stderr[-500:]}")
            raise
        except FileNotFoundError:
            print(f"  [ERROR] OMC executable not found at '{omc_path}'")
            raise

        # OMC writes <prefix>.fmu in the work directory
        src_fmu = os.path.join(work_dir, f"{prefix}.fmu")
        if not os.path.isfile(src_fmu):
            stderr_tail = (result.stderr or "")[-300:]
            stdout_tail = (result.stdout or "")[-300:]
            raise RuntimeError(
                f"OMC did not produce {prefix}.fmu in {work_dir}.\n"
                f"  stdout tail: {stdout_tail}\n"
                f"  stderr tail: {stderr_tail}"
            )

        # Destination filename
        dst_name = f"{prefix}.fmu"
        dst_path = os.path.join(output_dir, dst_name)
        shutil.move(src_fmu, dst_path)

    # Clean up the .mos script
    try:
        os.unlink(mos_script)
    except OSError:
        pass

    return dst_path


# ---------------------------------------------------------------------------
# Batch generation
# ---------------------------------------------------------------------------
def generate_all_fmus(output_dir: str, include_cs: bool = False) -> dict:
    """Generate all test FMUs from Modelica sources.

    Args:
        output_dir: Directory to write FMU files into.
        include_cs: If *True*, also generate Co-Simulation FMUs for compound
            models (used by behavioral verification).

    Returns:
        Dict mapping fixture names → dict with ``"path"`` and ``"type"``.
    """
    os.makedirs(output_dir, exist_ok=True)

    omc_path = find_omc()
    if omc_path is None:
        print("[WARN] OMC (omc) not found on PATH -- skipping FMU generation.")
        print("[WARN] Install OpenModelica (e.g. `apt install omc` on Ubuntu).")
        return {}

    print(f"Using OMC: {omc_path}")

    result: dict[str, dict] = {}

    for fixture_name, (model_source_stem, is_compound, dep_stems) in _MODELS.items():
        mo_path = os.path.join(_MODELICA_DIR, f"{model_source_stem}.mo")
        if not os.path.isfile(mo_path):
            print(f"  [SKIP] Modelica source not found: {mo_path}")
            continue

        # Resolve dependency paths
        dep_paths = [os.path.join(_MODELICA_DIR, f"{d}.mo") for d in dep_stems]
        dep_paths = [p for p in dep_paths if os.path.isfile(p)]

        # Model Exchange FMU
        try:
            fmu_path = generate_fmu(
                model_name=model_source_stem,
                mo_path=mo_path,
                output_dir=output_dir,
                dependency_mo_paths=dep_paths,
                fmi_type="me",
                output_prefix=fixture_name,
                omc_path=omc_path,
            )
            result[fixture_name] = {"path": fmu_path, "type": "me"}
            print(f"  [OK]   {fixture_name}.fmu")
        except Exception as exc:
            print(f"  [FAIL] {fixture_name}.fmu: {exc}")

        # Co-Simulation FMU (compound models only, when requested)
        if include_cs and is_compound:
            cs_prefix = f"{fixture_name}_CS"
            try:
                cs_path = generate_fmu(
                    model_name=model_source_stem,
                    mo_path=mo_path,
                    output_dir=output_dir,
                    dependency_mo_paths=dep_paths,
                    fmi_type="cs",
                    output_prefix=cs_prefix,
                    omc_path=omc_path,
                )
                result[cs_prefix] = {"path": cs_path, "type": "cs"}
                print(f"  [OK]   {cs_prefix}.fmu")
            except Exception as exc:
                print(f"  [FAIL] {cs_prefix}.fmu: {exc}")

    return result


# ---------------------------------------------------------------------------
# CLI entry point (compatible with existing usage)
# ---------------------------------------------------------------------------
def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate test FMU fixtures using the OpenModelica compiler.",
    )
    parser.add_argument(
        "output_dir",
        nargs="?",
        default=os.path.join(_HERE),
        help="Output directory (default: tests/fixtures/)",
    )
    parser.add_argument(
        "--cs",
        action="store_true",
        help="Also generate Co-Simulation FMUs for compound models",
    )
    args = parser.parse_args()

    fmus = generate_all_fmus(args.output_dir, include_cs=args.cs)
    if fmus:
        print(f"\nGenerated {len(fmus)} FMU(s) in {args.output_dir}:")
        for name, meta in fmus.items():
            print(f"  {name}: {meta['path']} ({meta['type']})")
    else:
        print("\nNo FMUs were generated.")


if __name__ == "__main__":
    main()