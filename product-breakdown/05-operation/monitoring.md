# Monitoring

## Build Report

The packager emits a machine-readable JSON build report when `-r/--report` is specified. The report contains:

- `tool_version` — Python version string
- `fmu_count` — Number of internal FMUs
- `variable_count` — Total wrapper boundary variables
- `connection_count` — Number of internal connections
- `algebraic_loop_count` — Number of detected SCCs
- `solver_type` — Solver policy string
- `solver_step_size` — Internal solver step size
- `communication_step` — Outer communication step size
- `warnings` — List of warnings (e.g., unsupported features, direction mismatches)
- `fmu_guids` — GUIDs of internal FMUs
- `wrapper_variables` — List of wrapper variable names

## FMI Status Codes

The generated wrapper returns standard FMI 2.0 status codes:
- `fmi2OK` — normal operation
- `fmi2Warning` — non-convergence of algebraic loops (operation continues)
- `fmi2Discard` — unsupported operations (FMU state, directional derivatives)
- `fmi2Error` — fatal errors (solver failure, initialization failure)

## Diagnostics

The FMI logger callback (provided by the master algorithm) receives diagnostic messages for:
- Wrapper creation and initialization
- Solver initialization success/failure
- Fixed-point iteration status
- Solver step failures

## Source

Derived from `src/cs_fmu_packager/packager.py` (BuildReport, write_build_report) and `src/cs_fmu_packager/codegen/fmi_interface.py` (log_message, status codes).