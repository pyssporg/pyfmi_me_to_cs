"""Shared pytest fixtures and helpers."""
from __future__ import annotations

import os
import shutil
import tempfile

import pytest


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