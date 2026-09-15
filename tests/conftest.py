"""Shared pytest fixtures and helpers."""
from __future__ import annotations

import os
import re
import shutil
import tempfile
import zipfile
from typing import Generator

import pytest

from pyssp_standard.standard.ssp1.codec.ssd_codec import Ssp1SsdCodec

from tests.helpers import build_ssp_document, make_fmu_bytes, make_test_fmu


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture
def fixtures_dir() -> str:
    """Return the path to pre-built test FMU fixtures."""
    return FIXTURES_DIR


@pytest.fixture
def fmu_fixture_path(fixtures_dir: str):
    """Return a function that creates a temp copy of a named fixture FMU.

    Usage:
        path = fmu_fixture_path("integrator")
        # path is a temp copy of tests/fixtures/integrator.fmu
    """
    _paths: list[str] = []

    def _load(name: str) -> str:
        src = os.path.join(fixtures_dir, f"{name}.fmu")
        if not os.path.exists(src):
            raise FileNotFoundError(f"Fixture FMU not found: {src}")
        dst = tempfile.mktemp(suffix=".fmu")
        shutil.copy2(src, dst)
        _paths.append(dst)
        return dst

    yield _load

    for p in _paths:
        if os.path.exists(p):
            os.unlink(p)


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