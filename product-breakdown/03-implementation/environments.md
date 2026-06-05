# Environments

## Build Environment

| Requirement | Version/Detail |
| --- | --- |
| Python | ≥3.10 |
| Operating System | Linux x86_64 (see AD-006) |
| C Compiler | GCC or Clang (C11 support) |
| CMake | ≥3.22 |
| vcpkg | Installed with `VCPKG_ROOT` environment variable set |
| SUNDIALS | Installed via vcpkg (arkode, nvecserial) |

## Runtime Environment (Generated FMU)

| Requirement | Detail |
| --- | --- |
| Operating System | Linux x86_64 |
| Libraries | Standard C library; no Python required |
| External Dependencies | None (all internal FMU binaries are embedded and loaded via dlopen) |

## Development Environment

| Requirement | Version/Detail |
| --- | --- |
| Python | ≥3.10 |
| pytest | ≥7.0 (optional dev dependency) |
| Operating System | Linux x86_64 recommended for full test suite |