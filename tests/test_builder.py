"""Unit tests for the CMake/vcpkg build integration (builder.py).

These tests exercise the build pipeline without a real vcpkg + SUNDIALS
installation by monkeypatching ``subprocess.run`` and providing minimal
fake vcpkg roots / build trees.
"""
from __future__ import annotations

import os
import subprocess

import pytest

from cs_fmu_packager.builder import (
    _find_vcpkg_root,
    _get_tool_versions,
    build_fmu,
)
from cs_fmu_packager.errors import BuildError


@pytest.fixture
def fake_vcpkg_root(tmp_path) -> str:
    """A vcpkg-shaped root containing the toolchain file."""
    root = tmp_path / "vcpkg"
    toolchain = root / "scripts" / "buildsystems"
    toolchain.mkdir(parents=True)
    (toolchain / "vcpkg.cmake").write_text("# fake toolchain")
    return str(root)


def _make_fake_runner(*, results: dict) -> object:
    """Return a ``subprocess.run`` stand-in that dispatches on argv[0].

    ``results`` maps an argv prefix (e.g. ``"cmake -S"``) to
    ``(returncode, stdout, stderr)``.  Tool-version queries used by
    ``_get_tool_versions`` are answered from defaults unless overridden.
    """
    versions = {
        "cmake --version": "cmake version 3.28.0\n",
        "gcc --version": "gcc (GCC) 13.2.0\n",
    }

    def _run(cmd, **kwargs):
        argv = " ".join(cmd)
        for prefix, (rc, out, err) in results.items():
            if argv.startswith(prefix):
                return subprocess.CompletedProcess(cmd, rc, out, err)
        if argv in versions:
            return subprocess.CompletedProcess(cmd, 0, versions[argv], "")
        if argv.endswith("--version"):
            return subprocess.CompletedProcess(cmd, 0, "Python 3.11.4\n", "")
        raise AssertionError(f"unexpected subprocess call: {argv!r}")

    return _run


class TestFindVcpkgRoot:
    def test_explicit_path(self, fake_vcpkg_root):
        assert _find_vcpkg_root(fake_vcpkg_root) == fake_vcpkg_root

    def test_explicit_missing_path_raises(self, tmp_path):
        missing = str(tmp_path / "nope")
        with pytest.raises(BuildError) as exc:
            _find_vcpkg_root(missing)
        assert "not found" in str(exc.value)

    def test_environment_variable(self, fake_vcpkg_root, monkeypatch):
        monkeypatch.delenv("VCPKG_ROOT", raising=False)
        monkeypatch.setenv("VCPKG_ROOT", fake_vcpkg_root)
        assert _find_vcpkg_root(None) == fake_vcpkg_root

    def test_common_path_fallback(self, tmp_path, monkeypatch):
        monkeypatch.delenv("VCPKG_ROOT", raising=False)
        home = tmp_path / "home"
        (home / "vcpkg").mkdir(parents=True)
        monkeypatch.setattr(
            "cs_fmu_packager.builder.os.path.expanduser",
            lambda p: p.replace("~", str(home)),
        )
        assert _find_vcpkg_root(None) == os.path.join(str(home), "vcpkg")

    def test_nothing_found_raises(self, tmp_path, monkeypatch):
        monkeypatch.delenv("VCPKG_ROOT", raising=False)
        monkeypatch.setattr(
            "cs_fmu_packager.builder.os.path.expanduser",
            lambda p: os.path.join(str(tmp_path), "none"),
        )
        monkeypatch.setattr(
            "cs_fmu_packager.builder.os.path.dirname",
            lambda p: os.path.join(str(tmp_path), "pkg", "src"),
        )
        monkeypatch.setattr(
            "cs_fmu_packager.builder.os.path.abspath",
            lambda p: p,
        )
        with pytest.raises(BuildError) as exc:
            _find_vcpkg_root(None)
        assert "vcpkg root not found" in str(exc.value)


class TestGetToolVersions:
    def test_all_tools_found(self, monkeypatch):
        def _run(cmd, **kwargs):
            name = cmd[0]
            out = {
                "cmake": "cmake version 3.28.0\n...",
                "gcc": "gcc (GCC) 13.2.0\n...",
            }.get(name, "Python 3.11.4\n")
            return subprocess.CompletedProcess(cmd, 0, out, "")

        monkeypatch.setattr("cs_fmu_packager.builder.subprocess.run", _run)
        versions = _get_tool_versions()
        assert "cmake" in versions and "cmake version" in versions["cmake"]
        assert "gcc" in versions and "GCC" in versions["gcc"]
        assert "python" in versions and versions["python"] == "Python 3.11.4"

    def test_missing_tools_reported(self, monkeypatch):
        def _run(cmd, **kwargs):
            raise FileNotFoundError(cmd[0])

        monkeypatch.setattr("cs_fmu_packager.builder.subprocess.run", _run)
        versions = _get_tool_versions()
        assert versions["cmake"] == "not found"
        assert versions["gcc"] == "not found"
        assert versions["python"] == "not found"


class TestBuildFmu:
    def test_missing_toolchain_raises(self, tmp_path, monkeypatch):
        root = str(tmp_path / "vcpkg")
        os.makedirs(root, exist_ok=True)
        monkeypatch.setattr(
            "cs_fmu_packager.builder._find_vcpkg_root", lambda arg: root
        )
        with pytest.raises(BuildError) as exc:
            build_fmu(
                source_dir=str(tmp_path / "src"),
                build_dir=str(tmp_path / "b"),
                vcpkg_root_arg=root,
            )
        assert "toolchain file not found" in str(exc.value)

    def test_cmake_configure_failure(self, tmp_path, fake_vcpkg_root, monkeypatch):
        runner = _make_fake_runner(
            results={"cmake -S": (1, "bad option", "configure exploded")}
        )
        monkeypatch.setattr("cs_fmu_packager.builder.subprocess.run", runner)
        with pytest.raises(BuildError) as exc:
            build_fmu(
                source_dir=str(tmp_path / "src"),
                build_dir=str(tmp_path / "b"),
                vcpkg_root_arg=fake_vcpkg_root,
            )
        assert "CMake configuration failed" in str(exc.value)
        assert "configure exploded" in str(exc.value)

    def test_cmake_build_failure(self, tmp_path, fake_vcpkg_root, monkeypatch):
        runner = _make_fake_runner(
            results={
                "cmake -S": (0, "configured", ""),
                "cmake --build": (2, "", "undefined reference to foo"),
            }
        )
        monkeypatch.setattr("cs_fmu_packager.builder.subprocess.run", runner)
        with pytest.raises(BuildError) as exc:
            build_fmu(
                source_dir=str(tmp_path / "src"),
                build_dir=str(tmp_path / "b"),
                vcpkg_root_arg=fake_vcpkg_root,
            )
        assert "CMake build failed" in str(exc.value)
        assert "undefined reference to foo" in str(exc.value)

    def test_so_not_found_after_successful_build(
        self, tmp_path, fake_vcpkg_root, monkeypatch
    ):
        runner = _make_fake_runner(
            results={
                "cmake -S": (0, "configured", ""),
                "cmake --build": (0, "built", ""),
                "file": (0, "ELF 64-bit LSB shared object", ""),
            }
        )
        monkeypatch.setattr("cs_fmu_packager.builder.subprocess.run", runner)
        with pytest.raises(BuildError) as exc:
            build_fmu(
                source_dir=str(tmp_path / "src"),
                build_dir=str(tmp_path / "b"),
                vcpkg_root_arg=fake_vcpkg_root,
            )
        assert ".so not found" in str(exc.value)

    def test_happy_path(self, tmp_path, fake_vcpkg_root, monkeypatch):
        build_dir = tmp_path / "b"
        so = build_dir / "binaries" / "linux64" / "myfmu.so"
        so.parent.mkdir(parents=True)
        so.write_bytes(b"\x7fELF")

        runner = _make_fake_runner(
            results={
                "cmake -S": (0, "configured", ""),
                "cmake --build": (0, "built", ""),
                "file": (0, "ELF 64-bit LSB shared object", ""),
            }
        )
        monkeypatch.setattr("cs_fmu_packager.builder.subprocess.run", runner)
        result = build_fmu(
            source_dir=str(tmp_path / "src"),
            build_dir=str(build_dir),
            vcpkg_root_arg=fake_vcpkg_root,
            fmu_name="myfmu",
        )
        assert result.success is True
        assert result.so_path == str(so)
        assert "myfmu" in result.so_path
        assert result.arch is not None
        assert result.tool_versions["python"] != "not found"

    def test_alternate_lib_prefix_so(self, tmp_path, fake_vcpkg_root, monkeypatch):
        """``lib<name>.so`` is accepted when ``<name>.so`` is absent."""
        build_dir = tmp_path / "b"
        so = build_dir / "binaries" / "linux64" / "libmyfmu.so"
        so.parent.mkdir(parents=True)
        so.write_bytes(b"\x7fELF")

        runner = _make_fake_runner(
            results={
                "cmake -S": (0, "configured", ""),
                "cmake --build": (0, "built", ""),
                "file": (0, "ELF 64-bit LSB shared object", ""),
            }
        )
        monkeypatch.setattr("cs_fmu_packager.builder.subprocess.run", runner)
        result = build_fmu(
            source_dir=str(tmp_path / "src"),
            build_dir=str(build_dir),
            vcpkg_root_arg=fake_vcpkg_root,
            fmu_name="myfmu",
        )
        assert result.so_path == str(so)

    def test_cmake_not_installed_raises(self, tmp_path, fake_vcpkg_root, monkeypatch):
        """FileNotFoundError from cmake configure surfaces a clear BuildError."""
        def _run(cmd, **kwargs):
            raise FileNotFoundError(cmd[0])

        monkeypatch.setattr("cs_fmu_packager.builder.subprocess.run", _run)
        with pytest.raises(BuildError) as exc:
            build_fmu(
                source_dir=str(tmp_path / "src"),
                build_dir=str(tmp_path / "b"),
                vcpkg_root_arg=fake_vcpkg_root,
            )
        assert "CMake not found" in str(exc.value)

    def test_cmake_configure_timeout_raises(self, tmp_path, fake_vcpkg_root, monkeypatch):
        def _run(cmd, **kwargs):
            if cmd[0] == "cmake" and "-S" in cmd:
                raise subprocess.TimeoutExpired(" ".join(cmd), timeout=300)
            return subprocess.CompletedProcess(cmd, 0, "version\n", "")

        monkeypatch.setattr("cs_fmu_packager.builder.subprocess.run", _run)
        with pytest.raises(BuildError) as exc:
            build_fmu(
                source_dir=str(tmp_path / "src"),
                build_dir=str(tmp_path / "b"),
                vcpkg_root_arg=fake_vcpkg_root,
            )
        assert "timed out" in str(exc.value)

    def test_build_timeout_raises(self, tmp_path, fake_vcpkg_root, monkeypatch):
        def _run(cmd, **kwargs):
            if cmd[0] == "cmake" and "--build" in cmd:
                raise subprocess.TimeoutExpired(" ".join(cmd), timeout=600)
            return subprocess.CompletedProcess(cmd, 0, "configured\n", "")

        monkeypatch.setattr("cs_fmu_packager.builder.subprocess.run", _run)
        with pytest.raises(BuildError) as exc:
            build_fmu(
                source_dir=str(tmp_path / "src"),
                build_dir=str(tmp_path / "b"),
                vcpkg_root_arg=fake_vcpkg_root,
            )
        assert "timed out" in str(exc.value)

    def test_file_command_unavailable_keeps_arch_none(
        self, tmp_path, fake_vcpkg_root, monkeypatch
    ):
        """A missing ``file`` tool must not fail the build; arch stays None."""
        build_dir = tmp_path / "b"
        so = build_dir / "binaries" / "linux64" / "myfmu.so"
        so.parent.mkdir(parents=True)
        so.write_bytes(b"\x7fELF")

        def _run(cmd, **kwargs):
            if cmd[0] == "file":
                raise FileNotFoundError("file")
            return subprocess.CompletedProcess(cmd, 0, "ok\n", "")

        monkeypatch.setattr("cs_fmu_packager.builder.subprocess.run", _run)
        result = build_fmu(
            source_dir=str(tmp_path / "src"),
            build_dir=str(build_dir),
            vcpkg_root_arg=fake_vcpkg_root,
            fmu_name="myfmu",
        )
        assert result.success is True
        assert result.so_path == str(so)
        assert result.arch is None

    def test_verbose_happy_path_emits_progress(self, tmp_path, fake_vcpkg_root, monkeypatch, capsys):
        """verbose=True prints the build stages to stdout."""
        build_dir = tmp_path / "b"
        so = build_dir / "binaries" / "linux64" / "myfmu.so"
        so.parent.mkdir(parents=True)
        so.write_bytes(b"\x7fELF")

        runner = _make_fake_runner(
            results={
                "cmake -S": (0, "configured", ""),
                "cmake --build": (0, "built", ""),
                "file": (0, "ELF 64-bit LSB shared object", ""),
            }
        )
        monkeypatch.setattr("cs_fmu_packager.builder.subprocess.run", runner)
        result = build_fmu(
            source_dir=str(tmp_path / "src"),
            build_dir=str(build_dir),
            vcpkg_root_arg=fake_vcpkg_root,
            fmu_name="myfmu",
            verbose=True,
        )
        assert result.success is True
        out = capsys.readouterr().out
        assert "Configuring CMake..." in out
        assert "CMake configuration succeeded." in out
        assert "CMake build succeeded." in out
        assert "Architecture:" in out