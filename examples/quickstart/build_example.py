#!/usr/bin/env python3
"""Build the runnable quickstart example.

Generates the two Model Exchange FMUs (``integrator``, ``gain``) from the
Modelica sources in ``models/`` using the OpenModelica compiler (``omc``),
then assembles a complete ``quickstart.ssp`` archive from the static
``SystemStructure.ssd`` plus the generated FMUs.

Prerequisites:
    - ``omc`` (OpenModelica compiler) on PATH
    - cs-fmu-packager installed (``pip install -e .``)

Usage::

    python build_example.py [output_dir]

Outputs ``<output_dir>/quickstart.ssp`` (default: this directory).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

_HERE = os.path.abspath(os.path.dirname(__file__))
_SSD = os.path.join(_HERE, "SystemStructure.ssd")
_MODELS_DIR = os.path.join(_HERE, "models")

_MODELS = {
    "integrator": "Integrator",
    "gain": "Gain",
}


def find_omc() -> str | None:
    return shutil.which("omc")


def _write_mos_script(model_name: str, mo_path: str, prefix: str) -> str:
    lines = [
        "loadModel(Modelica);",
        f'loadFile("{mo_path}");',
        f'buildModelFMU({model_name}, version="2.0", fmuType="me", '
        f'fileNamePrefix="{prefix}");',
        "getErrorString();",
    ]
    fd, path = tempfile.mkstemp(suffix=".mos", prefix=f"{prefix}_")
    with os.fdopen(fd, "w") as f:
        f.write("\n".join(lines) + "\n")
    return path


def _generate_fmu(model_name: str, prefix: str, output_dir: str) -> str:
    mos_script = _write_mos_script(
        model_name,
        os.path.join(_MODELS_DIR, f"{model_name}.mo"),
        prefix,
    )
    with tempfile.TemporaryDirectory() as work_dir:
        local_mos = os.path.join(work_dir, os.path.basename(mos_script))
        shutil.copy2(mos_script, local_mos)
        subprocess.run(
            ["omc", local_mos], cwd=work_dir, check=True,
            capture_output=True, text=True, timeout=120,
        )
        src = os.path.join(work_dir, f"{prefix}.fmu")
        if not os.path.isfile(src):
            raise RuntimeError(f"omc did not produce {prefix}.fmu")
        dst = os.path.join(output_dir, f"{prefix}.fmu")
        shutil.move(src, dst)
    try:
        os.unlink(mos_script)
    except OSError:
        pass
    return dst


def build_ssp(output_dir: str) -> str:
    os.makedirs(output_dir, exist_ok=True)
    omc = find_omc()
    if omc is None:
        print("[ERROR] omc not found on PATH. Install OpenModelica "
              "(e.g. `sudo apt install omc`) and try again.")
        sys.exit(1)
    print(f"Using omc: {omc}")

    for prefix, model in _MODELS.items():
        path = _generate_fmu(model, prefix, output_dir)
        print(f"  [OK] generated {path}")

    ssp_path = os.path.join(output_dir, "quickstart.ssp")
    with zipfile.ZipFile(ssp_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(_SSD, "SystemStructure.ssd")
        for prefix in _MODELS:
            zf.write(
                os.path.join(output_dir, f"{prefix}.fmu"),
                f"resources/{prefix}.fmu",
            )
    print(f"  [OK] assembled {ssp_path}")
    return ssp_path


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else _HERE
    build_ssp(os.path.abspath(out))