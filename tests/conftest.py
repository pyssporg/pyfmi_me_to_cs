"""Shared pytest fixtures and helpers."""
from __future__ import annotations

import os
import re
import tempfile
import zipfile
from typing import Generator

import pytest

from pyssp_standard.standard.ssp1.codec.ssd_codec import Ssp1SsdCodec

from tests.helpers import build_ssp_document, make_fmu_bytes


_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BUILD_TEST_DIR = os.path.join(_REPO_ROOT, "build", "test")


def _sanitize_path_segment(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name)


@pytest.fixture
def artifact_dir(request) -> str:
    """Persistent per-test artifact directory under ``build/test/``.

    Heavy pipeline tests (OMC FMU generation, packaging, simulation) write
    every intermediate and result here so they survive for manual review
    after the test run.  The directory is intentionally NOT cleaned up;
    the most recent run for a given test wins.
    """
    module = os.path.splitext(os.path.basename(request.module.__file__))[0]
    path = os.path.join(
        BUILD_TEST_DIR, _sanitize_path_segment(module), _sanitize_path_segment(request.node.name)
    )
    os.makedirs(path, exist_ok=True)
    return path


@pytest.fixture
def tmp_fmu_path() -> Generator[str, None, None]:
    """Yield a temporary .fmu path; cleaned up after the test."""
    fd, path = tempfile.mkstemp(suffix=".fmu")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def make_ssp():
    """Return a factory that writes a complete ``.ssp`` archive for testing.

    Usage::

        path = make_ssp(
            fmu_sources={"m00": "resources/m00.fmu", ...},
            fmu_files={"m00": b"<modelDescription...>"},
            connectors=[...],
            connections=[...],
        )
    """
    _paths: list[str] = []

    def _make(
        fmu_sources: dict[str, str],
        *,
        fmu_files: dict[str, bytes] | None = None,
        connectors: list[dict] | None = None,
        connections: list[tuple[str, str, str, str]] | None = None,
        parameters: list[tuple[str, str, object]] | None = None,
        annotations: list[tuple[str, object]] | None = None,
        name: str = "system",
        suffix: str = ".ssp",
    ) -> str:
        document = build_ssp_document(
            fmu_sources=fmu_sources,
            connectors=connectors,
            connections=connections,
            parameters=parameters,
            annotations=annotations,
            name=name,
        )
        fd, path = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        try:
            sentinel = object()

            def _fmu_bytes(cname: str):
                if fmu_files is not None and cname in fmu_files:
                    return fmu_files[cname]
                return sentinel

            with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("SystemStructure.ssd", Ssp1SsdCodec().serialize(document))
                for cname, source in fmu_sources.items():
                    member = re.sub(r"^\./", "", source)
                    data = _fmu_bytes(cname)
                    if data is sentinel:
                        data = make_fmu_bytes()
                    zf.writestr(member, data)
        except Exception:
            try:
                os.unlink(path)
            except OSError:
                pass
            raise
        _paths.append(path)
        return path

    yield _make

    for p in _paths:
        if os.path.exists(p):
            os.unlink(p)