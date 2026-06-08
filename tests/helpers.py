"""Shared test helper utilities."""
from __future__ import annotations

import zipfile


def make_test_fmu(path: str, model_description_xml: str) -> None:
    """Write a minimal FMU ZIP containing *model_description_xml* to *path*."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("modelDescription.xml", model_description_xml)