# Runbook

## Runtime Requirements

The generated Co-Simulation FMU has no runtime dependencies beyond the standard C library. It does not require Python, CMake, vcpkg, or any other build tool at runtime. Internal FMU shared libraries are loaded dynamically via `dlopen`.

## Known Error Conditions

| Error | Cause | Resolution |
| --- | --- | --- |
| SSP package not found | Invalid or missing path to `.ssp` archive | Verify the package path is correct and the file exists |
| Missing member or section | `.ssp` missing `SystemStructure.ssd` or a referenced `<Component source>` member | Check the archive layout against the SSD `source` URIs |
| FMI version not 2.0 | Input FMU uses FMI 1.0 or 3.0 | Use FMI 2.0 Model Exchange FMUs |
| Not a ModelExchange FMU | Input FMU is Co-Simulation only | Use a Model Exchange FMU for input |
| Variable not found in FMU | Package references a variable that doesn't exist in the FMU's modelDescription.xml | Check connector/connection names against the FMU metadata |
| Duplicate boundary name | Two system connectors with the same `name` | Rename one of the connectors |
| Step size > communication step | vendor annotation `stepSize` > `communicationStep` (or CLI override) | Set step size ≤ communication step |
| vcpkg root not found | CMake build cannot locate vcpkg | Set `VCPKG_ROOT` environment variable or pass `--vcpkg-root` |
| Build failed | CMake configure or build error | Check CMake output for diagnostic; verify CMake, GCC, and SUNDIALS are installed |
| Solver initialization failed | Internal solver (SUNDIALS ARKODE) could not be initialized | Check that internal FMUs provide valid continuous states |
| Fixed-point iteration did not converge | Algebraic loop could not be resolved within max_iterations | Increase max_iterations or tolerance; check if the loop is physically correct |

## Logging

- Set `-v`/`--verbose` flag for diagnostic output during packaging
- The generated FMU logs via FMI callback logger (if the master provides one)
- Non-convergence of algebraic loops is logged as `fmi2Warning`

## Source

Derived from `src/cs_fmu_packager/errors.py`, `src/cs_fmu_packager/builder.py`, and `src/cs_fmu_packager/cli.py`.