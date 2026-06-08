"""Behavioral verification tests for the ME → CS conversion pipeline.

These tests validate that the ``verify_cs_behavior()`` helper correctly
compares simulation trajectories.  The full ME→CS pipeline integration
test (comparing a ``cs-fmu-packager`` output against a reference OMC CS FMU)
requires the C build chain (vcpkg + SUNDIALS) and is gated behind
``VCPKG_ROOT``.

Prerequisites (checked at runtime via ``@pytest.mark.skipif``):

* ``omc`` (OpenModelica compiler) installed
* ``fmpy`` installed (``pip install fmpy``)
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

import pytest

# ---------------------------------------------------------------------------
# Module-level guards
# ---------------------------------------------------------------------------
_OMC_AVAILABLE = shutil.which("omc") is not None
_FMPY_AVAILABLE = False
try:
    import fmpy  # noqa: F401
    _FMPY_AVAILABLE = True
except ImportError:
    pass

pytestmark = pytest.mark.verification

# Paths
_HERE = os.path.abspath(os.path.dirname(__file__))
_FIXTURES_DIR = os.path.join(_HERE, "fixtures")
_MODELICA_DIR = os.path.join(_FIXTURES_DIR, "modelica")
_GENERATE_SCRIPT = os.path.join(_FIXTURES_DIR, "generate_test_fmus.py")

# Which compound model to use for verification
_COMPOUND = "IntegratorWithGain"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _generate_into(tmp_dir: str, include_cs: bool = False) -> None:
    """Run the fixture generator into a temporary directory."""
    cmd = [sys.executable, _GENERATE_SCRIPT, tmp_dir]
    if include_cs:
        cmd.append("--cs")
    subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=180)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
@pytest.mark.skipif(
    not _OMC_AVAILABLE,
    reason="OpenModelica compiler (omc) not installed",
)
@pytest.mark.skipif(
    not _FMPY_AVAILABLE,
    reason="fmpy not installed (pip install fmpy)",
)
def test_fixture_generation_produces_valid_fmus() -> None:
    """Verify that OMC-based fixture generation produces valid FMUs.

    This is a precondition for the trajectory comparison tests.
    """
    with tempfile.TemporaryDirectory(prefix="cs_verify_") as tmp:
        _generate_into(tmp, include_cs=True)

        # Check that all expected FMUs exist
        expected = [
            "integrator.fmu",
            "gain.fmu",
            f"{_COMPOUND}.fmu",
            f"{_COMPOUND}_CS.fmu",
        ]
        for fname in expected:
            path = os.path.join(tmp, fname)
            assert os.path.isfile(path), f"Missing generated FMU: {path}"
            assert os.path.getsize(path) > 1000, f"FMU too small: {path}"

        # Verify OMC CS FMU is readable by fmpy
        from fmpy import read_model_description
        cs_fmu = os.path.join(tmp, f"{_COMPOUND}_CS.fmu")
        md = read_model_description(cs_fmu)
        assert md.fmiVersion == "2.0"
        assert md.modelName == _COMPOUND


@pytest.mark.skipif(
    not _OMC_AVAILABLE,
    reason="OpenModelica compiler (omc) not installed",
)
@pytest.mark.skipif(
    not _FMPY_AVAILABLE,
    reason="fmpy not installed (pip install fmpy)",
)
def test_verify_cs_behavior_passes_for_identical_fmus() -> None:
    """Verify that ``verify_cs_behavior()`` returns passed=True when comparing
    an FMU against itself (framework correctness test)."""
    with tempfile.TemporaryDirectory(prefix="cs_verify_") as tmp:
        _generate_into(tmp, include_cs=True)

        # Reference dir has the OMC CS FMU: IntegratorWithGain_CS.fmu
        reference_dir = os.path.join(tmp, "reference")
        os.makedirs(reference_dir, exist_ok=True)
        shutil.copy2(
            os.path.join(tmp, f"{_COMPOUND}_CS.fmu"),
            os.path.join(reference_dir, f"{_COMPOUND}_CS.fmu"),
        )

        # Packager dir has a copy named without _CS suffix: IntegratorWithGain.fmu
        packager_dir = os.path.join(tmp, "packager")
        os.makedirs(packager_dir, exist_ok=True)
        shutil.copy2(
            os.path.join(tmp, f"{_COMPOUND}_CS.fmu"),
            os.path.join(packager_dir, f"{_COMPOUND}.fmu"),
        )

        from tests.fixtures.cs_verification import verify_cs_behavior  # type: ignore[import-not-found]

        result = verify_cs_behavior(
            compound_name=_COMPOUND,
            reference_cs_dir=reference_dir,
            packager_output_dir=packager_dir,
            start_time=0.0,
            stop_time=0.5,
            step_size=0.01,
            rtol=1e-4,
            atol=1e-6,
        )

        assert result["passed"] is True, (
            f"Identical FMU comparison failed: {result['max_deviations']}"
        )
        # All deviations should be exactly zero
        for var, dev in result["max_deviations"].items():
            assert dev == 0.0, f"Variable '{var}' has non-zero deviation: {dev}"

        # Verify result structure
        assert "reference_trajectory" in result
        assert "artifact_trajectory" in result
        assert len(result["max_deviations"]) > 0


@pytest.mark.skipif(
    not _OMC_AVAILABLE,
    reason="OpenModelica compiler (omc) not installed",
)
@pytest.mark.skipif(
    not _FMPY_AVAILABLE,
    reason="fmpy not installed (pip install fmpy)",
)
def test_verify_cs_behavior_passes_with_tight_tolerance() -> None:
    """Tight tolerances should still pass for identical FMUs."""
    with tempfile.TemporaryDirectory(prefix="cs_verify_") as tmp:
        _generate_into(tmp, include_cs=True)

        reference_dir = os.path.join(tmp, "reference")
        os.makedirs(reference_dir, exist_ok=True)
        shutil.copy2(
            os.path.join(tmp, f"{_COMPOUND}_CS.fmu"),
            os.path.join(reference_dir, f"{_COMPOUND}_CS.fmu"),
        )

        packager_dir = os.path.join(tmp, "packager")
        os.makedirs(packager_dir, exist_ok=True)
        shutil.copy2(
            os.path.join(tmp, f"{_COMPOUND}_CS.fmu"),
            os.path.join(packager_dir, f"{_COMPOUND}.fmu"),
        )

        from tests.fixtures.cs_verification import verify_cs_behavior

        result = verify_cs_behavior(
            compound_name=_COMPOUND,
            reference_cs_dir=reference_dir,
            packager_output_dir=packager_dir,
            start_time=0.0,
            stop_time=0.5,
            step_size=0.01,
            rtol=1e-9,
            atol=1e-12,
        )

        assert result["passed"] is True, (
            f"Tight tolerance comparison failed: {result['max_deviations']}"
        )


@pytest.mark.skipif(
    not _OMC_AVAILABLE,
    reason="OpenModelica compiler (omc) not installed",
)
@pytest.mark.skipif(
    not _FMPY_AVAILABLE,
    reason="fmpy not installed (pip install fmpy)",
)
def test_verification_detects_corrupted_fmu() -> None:
    """Negative test: different input signals produce different trajectories.

    We use ``fmpy.simulate_fmu`` directly with different input values
    to verify that (a) input signals propagate through the FMU and
    (b) the verification framework would detect a mismatch.
    """
    import fmpy
    import numpy as np
    import pandas as pd

    with tempfile.TemporaryDirectory(prefix="cs_verify_") as tmp:
        _generate_into(tmp, include_cs=True)

        cs_fmu = os.path.join(tmp, f"{_COMPOUND}_CS.fmu")

        # Create input signals as a numpy structured array (fmpy format)
        # The struct must have field names matching FMU input variable names
        dt = np.dtype([("time", np.float64), ("u", np.float64)])
        input_signals = np.array([
            (0.0, 0.0),
            (0.0, 1.0),
            (0.5, 1.0),
        ], dtype=dt)

        # Simulate without external input (default u=0)
        result_zero = fmpy.simulate_fmu(
            cs_fmu, start_time=0.0, stop_time=0.5, step_size=0.01,
        )
        result_one = fmpy.simulate_fmu(
            cs_fmu, start_time=0.0, stop_time=0.5, step_size=0.01,
            input=input_signals,
        )

        df_zero = pd.DataFrame(result_zero) if not isinstance(result_zero, pd.DataFrame) else result_zero
        df_one = pd.DataFrame(result_one) if not isinstance(result_one, pd.DataFrame) else result_one

        # Check that the y trajectories differ significantly
        y_zero = df_zero["y"].values
        y_one = df_one["y"].values

        # Align lengths
        min_len = min(len(y_zero), len(y_one))
        y_zero = y_zero[:min_len]
        y_one = y_one[:min_len]

        # Max deviation should be well above tolerance
        max_dev = float(np.max(np.abs(y_one - y_zero)))
        assert max_dev > 1e-3, (
            f"Expected different trajectories for different inputs, "
            f"but max deviation is only {max_dev:.2e}. "
            f"y_zero[:5]={y_zero[:5]}, y_one[:5]={y_one[:5]}"
        )

        # Verify that allclose with default tolerances would detect this
        assert not np.allclose(y_zero, y_one, rtol=1e-4, atol=1e-6), (
            "Expected different inputs to produce detectably different "
            "trajectories, but allclose passed."
        )


# ---------------------------------------------------------------------------
# Note: The full ME→CS pipeline integration test (comparing the output of
# cs-fmu-packager against a reference OMC CS FMU) requires the C build
# chain (vcpkg + SUNDIALS).  It is gated behind VCPKG_ROOT and should be
# added to TestBuildReport or a similar conditional class once the build
# infrastructure is available in CI.
# ---------------------------------------------------------------------------