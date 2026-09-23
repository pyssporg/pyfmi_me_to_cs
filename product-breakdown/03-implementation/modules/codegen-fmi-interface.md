# Module: codegen/fmi_interface

**File:** `src/cs_fmu_packager/codegen/fmi_interface.py`

## Responsibility

Generates `fmi2_interface.c` — the main FMI 2.0 Co-Simulation entry point implementation. Implements all required FMI 2.0 CS functions using the wrapper state machine, internal FMU loading via `dlopen`/`dlsym`, variable mapping, and solver orchestration.

## Key Functions

| Function | Description |
| --- | --- |
| `generate_fmi_interface_impl(spec, mapping)` | Generate the fmi2_interface.c content |
| `_variable_mapping_init_code(...)` | Generate C init code that populates a VariableMapping array |

## Generated C Structures

| Structure | Description |
| --- | --- |
| `WrapperState` | Enum for state machine (Instantiated, InitializationMode, StepComplete, StepInProgress, Terminated, Error) |
| `InternalFMU` | Per-internal-FMU state: libHandle, function pointers, component handle |
| `VariableMapping` | Variable value reference, value union, FMU pointer |
| `WrapperInstance` | Top-level per-instance state: all arrays, solver state, callbacks |

## Generated FMI 2.0 CS Functions

- `fmi2GetTypesPlatform`, `fmi2GetVersion`
- `fmi2SetDebugLogging`
- `fmi2Instantiate` (allocates wrapper, loads internal FMUs via dlsym, populates variable mappings)
- `fmi2FreeInstance` (releases all resources)
- `fmi2SetupExperiment`, `fmi2EnterInitializationMode`, `fmi2ExitInitializationMode`
- `fmi2Terminate`, `fmi2Reset`
- `fmi2GetReal`/`fmi2SetReal`, `fmi2GetInteger`/`fmi2SetInteger`, `fmi2GetBoolean`/`fmi2SetBoolean`, `fmi2GetString`/`fmi2SetString`
- `fmi2DoStep` (push boundary inputs → integrate coupled system via `solver_step` → re-resolve coupling at final state → update outputs; coupling itself is resolved inside `combined_rhs`)
- `fmi2CancelStep`
- Status inquiry functions

## Source

- `src/cs_fmu_packager/codegen/fmi_interface.py` (1,230 lines of generated template)