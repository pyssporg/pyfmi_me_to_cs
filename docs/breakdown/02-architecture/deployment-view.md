# Deployment View

## Platform Support (v1)

- **Target:** Linux x86_64 only
- **Build host:** Linux x86_64 with CMake, GCC/Clang, vcpkg, SUNDIALS
- **Runtime:** Any Linux x86_64 system; no Python or special runtime required
- **Supported cross-platform:** Not in v1 (see AD-006)

## Generated FMU Archive Structure

The packaged Co-Simulation FMU follows the FMI standard directory convention:

```
output.fmu
├── modelDescription.xml       # FMI 2.0 Co-Simulation model description
├── binaries/
│   └── linux64/
│       └── <fmu_name>.so      # Compiled wrapper shared library
└── resources/
    ├── <fmu_id_1>.fmu         # Embedded internal ME FMU (byte-for-byte copy)
    ├── <fmu_id_2>.fmu         # Embedded internal ME FMU
    └── ...                    # All internal FMUs
```

## FMI Standard Directory Convention

The `binaries/<platform>/` directory follows the FMI 2.0 standard where:
- `linux64` — Linux x86_64 (64-bit)
- Future platforms: `win64` (Windows x86_64), `darwin64` (macOS ARM/x86_64)

## Deterministic Assembly

- ZIP entries use fixed timestamps (Jan 1, 2020 00:00:00 UTC).
- ZIP entries are written in sorted order.
- modelDescription.xml includes a generation timestamp (exceptions: determinism).
- GUID is derived deterministically from spec content via MD5.

## Relevant Decisions

- AD-004: Embedded FMU Resources (self-contained FMU)
- AD-006: Linux x86_64 Only (v1)