"""FMU inspection and modelDescription.xml parser.

Opens an FMI 2.0 Model Exchange FMU archive, validates its structure,
and extracts all metadata from modelDescription.xml.

Uses pyssp_standard for full typed dataclass access to FMI 2.0 model
description elements.
"""

from __future__ import annotations

import os

from pyssp_standard.fmu import FMU
from pyssp_standard.standard.fmi2.model.model_description import (
    Fmi2ModelDescriptionDocument,
)

from cs_fmu_packager.errors import FmuInspectionError


def inspect_fmu(path: str) -> Fmi2ModelDescriptionDocument:
    """Open an FMU archive and return its parsed model description.

    Args:
        path: Path to the .fmu file.

    Returns:
        Fmi2ModelDescriptionDocument with parsed modelDescription.xml contents.

    Raises:
        FmuInspectionError: If the FMU cannot be read or validated.
    """
    if not os.path.exists(path):
        raise FmuInspectionError(f"FMU file not found: {path}")

    if not path.endswith(".fmu"):
        raise FmuInspectionError(f"File is not an FMU (expected .fmu extension): {path}")

    # Fork-based parsing via pyssp_standard FMU context manager
    try:
        with FMU(path, mode='r') as fmu:
            md = fmu.model_description
            # Detect missing modelDescription.xml (md.path won't exist)
            if not md.path.exists():
                raise FmuInspectionError(f"FMU {path}: missing modelDescription.xml")
            doc = md.load_document()
    except FmuInspectionError:
        raise
    except Exception as e:
        msg = str(e)
        if "BadZipFile" in type(e).__name__ or "not a zip file" in msg.lower():
            raise FmuInspectionError(f"FMU {path}: not a valid ZIP archive") from e
        if "ParseError" in type(e).__name__:
            raise FmuInspectionError(f"FMU {path}: invalid modelDescription.xml: {e}") from e
        raise FmuInspectionError(f"Failed to read FMU {path}: {e}") from e

    # Validate FMI version
    if doc.fmi_version != "2.0":
        raise FmuInspectionError(
            f"FMU {path}: unsupported FMI version '{doc.fmi_version}', expected '2.0'"
        )

    # Validate that this is a ModelExchange FMU
    if doc.interface_type != "ModelExchange":
        raise FmuInspectionError(
            f"FMU {path}: not a ModelExchange FMU (found type: {doc.interface_type})"
        )

    return doc
