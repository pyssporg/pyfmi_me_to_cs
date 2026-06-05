# Module: builder

**File:** `src/cs_fmu_packager/builder.py`

## Responsibility

CMake + vcpkg build integration. Configures and runs CMake builds with vcpkg toolchain support for compiling the generated C wrapper code.

## Key Functions

| Function | Description |
| --- | --- |
| `build_fmu(source_dir, build_dir, ...)` | Configure and build the generated C wrapper using CMake + vcpkg |
| `_find_vcpkg_root(vcpkg_root_arg)` | Locate the vcpkg root directory (CLI arg → env var → common paths) |
| `_get_tool_versions()` | Capture versions of cmake, gcc, and python for build report |

## Build Steps

1. Locate vcpkg root and toolchain file
2. Run `cmake -S <source> -B <build> -DCMAKE_TOOLCHAIN_FILE=...`
3. Run `cmake --build <build> --config Release`
4. Locate resulting `.so` in `binaries/linux64/`
5. Verify architecture via `file` command

## BuildResult Dataclass

| Field | Description |
| --- | --- |
| `success` | Build success flag |
| `so_path` | Path to the compiled `.so` |
| `build_dir` | CMake build directory |
| `cmake_output` | CMake configure output |
| `build_output` | CMake build output |
| `arch` | Architecture string from `file` command |
| `tool_versions` | Dict of tool version strings |

## Source

- `src/cs_fmu_packager/builder.py` (236 lines)

## Related Tests

- `tests/test_end_to_end.py` — Conditional on VCPKG_ROOT being set