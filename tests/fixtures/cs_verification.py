"""Helpers for behavioral verification of the ME → CS conversion pipeline.

Provides :func:`verify_cs_behavior` which simulates both a reference CS FMU
(directly exported by OMC) and an artifact CS FMU (produced by the project's
own ``cs-fmu-packager`` pipeline) and compares their output trajectories
using configurable numerical tolerances.
"""

from __future__ import annotations

import os
from typing import Optional


def verify_cs_behavior(
    compound_name: str,
    reference_cs_dir: str,
    packager_output_dir: str,
    start_time: float = 0.0,
    stop_time: float = 1.0,
    step_size: float = 0.01,
    rtol: float = 1e-4,
    atol: float = 1e-6,
) -> dict:
    """Simulate both reference and artifact CS FMUs and compare trajectories.

    Args:
        compound_name:
            Name of the compound model (e.g. ``"IntegratorWithGain"``).
        reference_cs_dir:
            Directory containing the directly-exported OMC CS FMU
            (e.g. ``IntegratorWithGain_CS.fmu``).
        packager_output_dir:
            Directory containing the ``cs-fmu-packager``-produced CS FMU
            (e.g. ``IntegratorWithGain.fmu`` — the ME→CS converted artifact).
        start_time, stop_time, step_size:
            Simulation parameters (passed to ``fmpy.simulate_fmu``).
        rtol, atol:
            Relative and absolute tolerances for
            :func:`numpy.allclose`.

    Returns:
        A dict with keys:

        - **passed** (*bool*) — *True* if all variables match within tolerance.
        - **max_deviations** (*dict[str, float]*) — Per-variable maximum absolute
          deviation (or empty dict if no output variables).
        - **max_relative_deviations** (*dict[str, float]*) — Per-variable maximum
          relative deviation.
        - **reference_trajectory** (*pandas.DataFrame*) — Output from the
          reference (direct OMC CS) FMU.
        - **artifact_trajectory** (*pandas.DataFrame*) — Output from the
          artifact (packager-converted) FMU.

    Raises:
        ImportError: If ``fmpy`` or ``numpy`` or ``pandas`` are not installed.
        FileNotFoundError: If either FMU cannot be located.
        RuntimeError: If the two simulations have no common output variables.
    """
    # Lazy imports so the module is importable without fmpy/numpy/pandas
    try:
        import fmpy
    except ImportError:
        raise ImportError(
            "fmpy is required for behavioral verification. "
            "Install it with: pip install fmpy"
        )

    try:
        import numpy as np
    except ImportError:
        raise ImportError("numpy is required for behavioral verification.")

    # Locate both FMU files
    ref_fmu = _locate_fmu(compound_name, reference_cs_dir, suffix="_CS")
    art_fmu = _locate_fmu(compound_name, packager_output_dir, suffix="")

    # Simulate both
    ref_result = fmpy.simulate_fmu(
        ref_fmu,
        start_time=start_time,
        stop_time=stop_time,
        step_size=step_size,
    )
    art_result = fmpy.simulate_fmu(
        art_fmu,
        start_time=start_time,
        stop_time=stop_time,
        step_size=step_size,
    )

    ref_df = _ensure_dataframe(ref_result)
    art_df = _ensure_dataframe(art_result)

    # Identify common columns (excluding time)
    common = set(ref_df.columns) & set(art_df.columns)
    common = {c for c in common if c.lower() != "time"}

    if not common:
        raise RuntimeError(
            f"No common output variables between reference ({list(ref_df.columns)}) "
            f"and artifact ({list(art_df.columns)}) trajectories."
        )

    # Compare each variable
    max_deviations: dict[str, float] = {}
    max_relative_deviations: dict[str, float] = {}

    all_passed = True
    for var in sorted(common):
        ref_vals = ref_df[var].values
        art_vals = art_df[var].values

        # Align lengths (truncate to the shorter)
        min_len = min(len(ref_vals), len(art_vals))
        ref_vals = ref_vals[:min_len]
        art_vals = art_vals[:min_len]

        abs_diff = np.abs(ref_vals - art_vals)
        max_abs = float(np.max(abs_diff))
        max_deviations[var] = max_abs

        # Relative: avoid division by zero
        denom = np.abs(ref_vals)
        denom[denom < 1e-15] = 1.0
        rel_diff = abs_diff / denom
        max_rel = float(np.max(rel_diff))
        max_relative_deviations[var] = max_rel

        if not np.allclose(ref_vals, art_vals, rtol=rtol, atol=atol):
            all_passed = False

    return {
        "passed": all_passed,
        "max_deviations": max_deviations,
        "max_relative_deviations": max_relative_deviations,
        "reference_trajectory": ref_df,
        "artifact_trajectory": art_df,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _locate_fmu(
    compound_name: str,
    directory: str,
    suffix: str = "",
) -> str:
    """Locate an FMU file by compound name and optional suffix.

    Tries both ``<compound_name><suffix>.fmu`` and
    ``*{compound_name}*CS*.fmu`` patterns.
    """
    # Direct match
    direct = os.path.join(directory, f"{compound_name}{suffix}.fmu")
    if os.path.isfile(direct):
        return direct

    # Glob-style fallback (for packager output that may have different name)
    import glob
    candidates = glob.glob(os.path.join(directory, f"*{compound_name}*"))
    if suffix:
        candidates = [c for c in candidates if suffix.replace("_", "") in c]
    if candidates:
        return candidates[0]

    raise FileNotFoundError(
        f"Could not locate FMU for compound '{compound_name}' "
        f"with suffix '{suffix}' in '{directory}'."
        f"\n  Tried: {direct}"
    )


def _ensure_dataframe(result) -> "pandas.DataFrame":
    """Normalise the result of ``fmpy.simulate_fmu`` to a DataFrame.

    ``fmpy.simulate_fmu`` may return a ``pandas.DataFrame`` or a
    ``numpy.recarray`` depending on input types.  This helper converts
    both to a standard ``pandas.DataFrame``.
    """
    import pandas as pd

    if isinstance(result, pd.DataFrame):
        return result
    return pd.DataFrame(result)