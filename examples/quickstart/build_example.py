"""Build the quickstart SSP and convert it to one Co-Simulation FMU.

Generates the two Model Exchange FMUs from ``models/`` with ``omc``, packages
them with ``SystemStructure.ssd`` into ``quickstart.ssp`` through
``pyssp_standard.SSP``, then converts that package to ``quickstart.fmu`` with
``python -m cs_fmu_packager``.

Run from the workspace root:

    python repos/pyfmi_me_to_cs/examples/quickstart/build_example.py

Everything is written under ``build/examples/quickstart/`` unless ``--out`` is
given.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from pyssp_standard import SSP

EXAMPLE_DIR = Path(__file__).resolve().parent
SSD = EXAMPLE_DIR / "SystemStructure.ssd"
MODELS_DIR = EXAMPLE_DIR / "models"
COMPONENTS = {"m00": ("Integrator", "integrator"), "m01": ("Gain", "gain")}
DEFAULT_OUT = Path("build/examples/quickstart")


def _run(command: list[str], *, cwd: str | None = None) -> None:
    try:
        subprocess.run(command, cwd=cwd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as error:
        raise SystemExit((error.stderr or error.stdout).strip()) from error


def _build_fmu(model: str, prefix: str, output_dir: Path) -> Path:
    script = (
        "loadModel(Modelica);\n"
        f'loadFile("{MODELS_DIR / f"{model}.mo"}");\n'
        f'buildModelFMU({model}, version="2.0", fmuType="me", '
        f'fileNamePrefix="{prefix}");\n'
        "getErrorString();\n"
    )
    with tempfile.TemporaryDirectory() as work:
        mos = Path(work) / f"{prefix}.mos"
        mos.write_text(script, encoding="utf-8")
        _run(["omc", mos.name], cwd=work)
        source = Path(work) / f"{prefix}.fmu"
        target = output_dir / source.name
        shutil.move(source, target)
    return target


def _assemble_ssp(output_dir: Path, fmus: dict[str, Path]) -> Path:
    ssp_path = output_dir / "quickstart.ssp"
    with SSP(ssp_path, mode="w") as ssp:
        # The SSD is authored input, so it goes to the archive root as-is.
        ssp.runtime.add_file(SSD, target_name="SystemStructure.ssd")
        for fmu in fmus.values():
            ssp.add_resource(fmu)
    return ssp_path


def _to_cs_fmu(ssp_path: Path) -> Path:
    fmu_path = ssp_path.with_suffix(".fmu")
    _run(
        [
            sys.executable,
            "-m",
            "cs_fmu_packager",
            str(ssp_path),
            "-o",
            str(fmu_path),
        ]
    )
    return fmu_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help=f"output directory (default: {DEFAULT_OUT})",
    )
    args = parser.parse_args()

    if shutil.which("omc") is None:
        raise SystemExit("omc is required (OpenModelica compiler)")

    args.out.mkdir(parents=True, exist_ok=True)
    fmus = {
        component: _build_fmu(model, prefix, args.out)
        for component, (model, prefix) in COMPONENTS.items()
    }
    for fmu in fmus.values():
        print(fmu)

    ssp_path = _assemble_ssp(args.out, fmus)
    print(ssp_path)
    print(_to_cs_fmu(ssp_path))


if __name__ == "__main__":
    main()
