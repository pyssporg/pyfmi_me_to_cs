"""Shared pytest fixtures and helpers."""
from __future__ import annotations

import os
import shutil
import tempfile
import textwrap
from typing import Callable, Generator

import pytest

from tests.helpers import make_test_fmu


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
def spec_file() -> Callable[[str], str]:
    """Return a function that writes TOML content to a temp file and returns its path."""
    _paths: list[str] = []

    def _write(content: str) -> str:
        fd, path = tempfile.mkstemp(suffix=".toml")
        with os.fdopen(fd, "w") as f:
            f.write(textwrap.dedent(content))
        _paths.append(path)
        return path

    yield _write

    for p in _paths:
        if os.path.exists(p):
            os.unlink(p)