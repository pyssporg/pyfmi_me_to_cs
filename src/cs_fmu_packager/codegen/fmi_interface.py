"""Generate fmi2_interface.c - the main FMI 2.0 CS implementation."""
from __future__ import annotations

from cs_fmu_packager.models import MappedVariable, MappingTable, PackageSpec


def _variable_mapping_init_code(
    varname: str,
    vars_list: list[MappedVariable],
    indent: str,
) -> str:
    """Generate C init code that populates a VariableMapping array."""
    lines: list[str] = []
    for idx, var in enumerate(vars_list):
        fmu_ptr = "NULL"
        fmu_idx = -1
        if var.causality == "input" or var.causality == "parameter":
            if var.target_fmu is not None:
                fmu_ptr = f"&inst->internal_fmus[idx_{var.target_fmu}]"
        elif var.causality == "output":
            if var.source_fmu is not None:
                fmu_ptr = f"&inst->internal_fmus[idx_{var.source_fmu}]"

        lines.append(
            f'{indent}{varname}[{idx}].vr = {var.target_value_reference if var.causality in ("input","parameter") else var.source_value_reference or 0};'
        )

        var_type_lower = (var.variable_type or "Real").lower()
        val_field = {"real": "r", "integer": "i", "boolean": "b", "string": "s"}.get(
            var_type_lower, "r"
        )
        start_val = var.start
        if start_val is not None:
            if val_field == "i":
                lines.append(
                    f'{indent}{varname}[{idx}].value.{val_field} = {int(start_val)};'
                )
            elif val_field == "b":
                lines.append(
                    f'{indent}{varname}[{idx}].value.{val_field} = {"fmi2True" if start_val else "fmi2False"};'
                )
            elif val_field == "s":
                lines.append(
                    f'{indent}{varname}[{idx}].value.{val_field} = strdup("{start_val}");'
                )
            else:
                lines.append(
                    f'{indent}{varname}[{idx}].value.{val_field} = {start_val};'
                )

    return "\n".join(lines)


def generate_fmi_interface_impl(spec: PackageSpec, mapping: MappingTable) -> str:
    """Generate the fmi2_interface.c implementation.

    This is the main FMI 2.0 Co-Simulation entry point implementation.
    It implements all required FMI 2.0 CS functions using the wrapper
    state machine, internal FMU loading, and variable mapping.
    """
    fmu_name = spec.metadata.get("identifier", "cs_fmu")
    fmu_guid = spec.metadata.get("guid", "default-guid")
    num_fmus = len(spec.fmus)
    num_inputs = len(mapping.wrapper_inputs)
    num_outputs = len(mapping.wrapper_outputs)
    num_params = len(mapping.wrapper_parameters)
    num_connections = len(mapping.connections)

    # Count typed variables
    def _count_type(vars_list: list[MappedVariable], causality: str, vtype: str) -> int:
        return len(
            [v for v in vars_list if v.causality == causality and v.variable_type == vtype]
        )

    all_real_inputs = _count_type(mapping.wrapper_inputs, "input", "Real")
    all_int_inputs = _count_type(mapping.wrapper_inputs, "input", "Integer")
    all_bool_inputs = _count_type(mapping.wrapper_inputs, "input", "Boolean")
    all_str_inputs = _count_type(mapping.wrapper_inputs, "input", "String")
    all_real_outputs = _count_type(mapping.wrapper_outputs, "output", "Real")
    all_int_outputs = _count_type(mapping.wrapper_outputs, "output", "Integer")
    all_bool_outputs = _count_type(mapping.wrapper_outputs, "output", "Boolean")
    all_str_outputs = _count_type(mapping.wrapper_outputs, "output", "String")
    all_real_params = _count_type(mapping.wrapper_parameters, "parameter", "Real")
    all_int_params = _count_type(mapping.wrapper_parameters, "parameter", "Integer")
    all_bool_params = _count_type(mapping.wrapper_parameters, "parameter", "Boolean")
    all_str_params = _count_type(mapping.wrapper_parameters, "parameter", "String")

    # Build FMU index names for C code
    fmu_idx_defs = []
    for fmu_id in spec.fmus:
        fmu_idx_defs.append(f"    int idx_{fmu_id} = -1;")
    fmu_idx_assigns = []
    for idx, fmu_id in enumerate(spec.fmus):
        fmu_idx_assigns.append(f"    idx_{fmu_id} = {idx};")

    # Build FMU loading code
    fmu_load_blocks = []
    for idx, (fmu_id, fmu_ref) in enumerate(spec.fmus.items()):
        fmu_load_blocks.append(
            f"""    /* Load FMU: {fmu_id} */
    {{
        InternalFMU* fmu = &inst->internal_fmus[{idx}];
        fmu->nx = 0;  /* will be set from getContinuousStates during init */
        strncpy(fmu->instance_name, "{fmu_id}", sizeof(fmu->instance_name) - 1);

        /* Build path to the FMU shared library */
        char lib_path[MAX_RESOURCE_PATH];
        snprintf(lib_path, sizeof(lib_path),
                 "resources/%s/binaries/linux64/*.so", "{fmu_id}");

        fmu->libHandle = dlopen(lib_path, RTLD_NOW | RTLD_LOCAL);
        if (fmu->libHandle == NULL) {{
            log_message(inst, fmi2Error, "init",
                        "Failed to dlopen internal FMU '%s': %s", "{fmu_id}", dlerror());
            /* Cleanup already loaded FMUs */
            for (int k = 0; k < {idx}; k++) {{
                if (inst->internal_fmus[k].libHandle) dlclose(inst->internal_fmus[k].libHandle);
            }}
            free(inst->internal_fmus);
            free(inst);
            return NULL;
        }}

        /* Resolve FMI 2.0 ME function pointers */
        fmu->instantiateME = (fmi2InstantiateME_f)dlsym(fmu->libHandle, "fmi2Instantiate");
        if (fmu->instantiateME == NULL) {{
            /* Try with modelIdentifier prefix */
            fmu->instantiateME = (fmi2InstantiateME_f)dlsym(fmu->libHandle, "{fmu_id}_fmi2Instantiate");
        }}
        fmu->setReal = (fmi2SetReal_f)dlsym(fmu->libHandle, "fmi2SetReal");
        if (fmu->setReal == NULL) fmu->setReal = (fmi2SetReal_f)dlsym(fmu->libHandle, "{fmu_id}_fmi2SetReal");
        fmu->getReal = (fmi2GetReal_f)dlsym(fmu->libHandle, "fmi2GetReal");
        if (fmu->getReal == NULL) fmu->getReal = (fmi2GetReal_f)dlsym(fmu->libHandle, "{fmu_id}_fmi2GetReal");
        fmu->getDerivatives = (fmi2GetDerivatives_f)dlsym(fmu->libHandle, "fmi2GetDerivatives");
        if (fmu->getDerivatives == NULL) fmu->getDerivatives = (fmi2GetDerivatives_f)dlsym(fmu->libHandle, "{fmu_id}_fmi2GetDerivatives");
        fmu->setTime = (fmi2SetTime_f)dlsym(fmu->libHandle, "fmi2SetTime");
        if (fmu->setTime == NULL) fmu->setTime = (fmi2SetTime_f)dlsym(fmu->libHandle, "{fmu_id}_fmi2SetTime");
        fmu->setContinuousStates = (fmi2SetContinuousStates_f)dlsym(fmu->libHandle, "fmi2SetContinuousStates");
        if (fmu->setContinuousStates == NULL) fmu->setContinuousStates = (fmi2SetContinuousStates_f)dlsym(fmu->libHandle, "{fmu_id}_fmi2SetContinuousStates");
        fmu->getContinuousStates = (fmi2GetContinuousStates_f)dlsym(fmu->libHandle, "fmi2GetContinuousStates");
        if (fmu->getContinuousStates == NULL) fmu->getContinuousStates = (fmi2GetContinuousStates_f)dlsym(fmu->libHandle, "{fmu_id}_fmi2GetContinuousStates");
        fmu->initialize = (fmi2EnterInitializationMode_f)dlsym(fmu->libHandle, "fmi2EnterInitializationMode");
        if (fmu->initialize == NULL) fmu->initialize = (fmi2EnterInitializationMode_f)dlsym(fmu->libHandle, "{fmu_id}_fmi2EnterInitializationMode");
        fmu->terminate = (fmi2Terminate_f)dlsym(fmu->libHandle, "fmi2Terminate");
        if (fmu->terminate == NULL) fmu->terminate = (fmi2Terminate_f)dlsym(fmu->libHandle, "{fmu_id}_fmi2Terminate");
        fmu->freeInstance = (fmi2FreeInstance_f)dlsym(fmu->libHandle, "fmi2FreeInstance");
        if (fmu->freeInstance == NULL) fmu->freeInstance = (fmi2FreeInstance_f)dlsym(fmu->libHandle, "{fmu_id}_fmi2FreeInstance");
        fmu->setInteger = (fmi2SetInteger_f)dlsym(fmu->libHandle, "fmi2SetInteger");
        if (fmu->setInteger == NULL) fmu->setInteger = (fmi2SetInteger_f)dlsym(fmu->libHandle, "{fmu_id}_fmi2SetInteger");
        fmu->getInteger = (fmi2GetInteger_f)dlsym(fmu->libHandle, "fmi2GetInteger");
        if (fmu->getInteger == NULL) fmu->getInteger = (fmi2GetInteger_f)dlsym(fmu->libHandle, "{fmu_id}_fmi2GetInteger");
        fmu->setBoolean = (fmi2SetBoolean_f)dlsym(fmu->libHandle, "fmi2SetBoolean");
        if (fmu->setBoolean == NULL) fmu->setBoolean = (fmi2SetBoolean_f)dlsym(fmu->libHandle, "{fmu_id}_fmi2SetBoolean");
        fmu->getBoolean = (fmi2GetBoolean_f)dlsym(fmu->libHandle, "fmi2GetBoolean");
        if (fmu->getBoolean == NULL) fmu->getBoolean = (fmi2GetBoolean_f)dlsym(fmu->libHandle, "{fmu_id}_fmi2GetBoolean");
        fmu->setString = (fmi2SetString_f)dlsym(fmu->libHandle, "fmi2SetString");
        if (fmu->setString == NULL) fmu->setString = (fmi2SetString_f)dlsym(fmu->libHandle, "{fmu_id}_fmi2SetString");
        fmu->getString = (fmi2GetString_f)dlsym(fmu->libHandle, "fmi2GetString");
        if (fmu->getString == NULL) fmu->getString = (fmi2GetString_f)dlsym(fmu->libHandle, "{fmu_id}_fmi2GetString");

        if (fmu->instantiateME == NULL) {{
            log_message(inst, fmi2Error, "init",
                        "fmi2Instantiate not found in FMU '%s'", "{fmu_id}");
            dlclose(fmu->libHandle);
            for (int k = 0; k < {idx}; k++) {{
                if (inst->internal_fmus[k].libHandle) dlclose(inst->internal_fmus[k].libHandle);
            }}
            free(inst->internal_fmus);
            free(inst);
            return NULL;
        }}

        /* Instantiate the internal FMU */
        fmu->component = fmu->instantiateME(
            fmu->instance_name,
            fmi2ModelExchange,
            "{fmu_guid}",
            "resources",
            NULL,
            fmi2False,
            fmi2False
        );

        if (fmu->component == NULL) {{
            log_message(inst, fmi2Error, "init",
                        "fmi2Instantiate failed for FMU '%s'", "{fmu_id}");
            dlclose(fmu->libHandle);
            for (int k = 0; k < {idx}; k++) {{
                if (inst->internal_fmus[k].libHandle) dlclose(inst->internal_fmus[k].libHandle);
            }}
            free(inst->internal_fmus);
            free(inst);
            return NULL;
        }}

        /* Initialize the internal FMU */
        if (fmu->initialize) {{
            fmu->initialize(fmu->component);
        }}

        /* Get number of continuous states */
        if (fmu->getContinuousStates) {{
            fmu2Real dummy[1];
            fmu->getContinuousStates(fmu->component, dummy, 0);
            /* nx known from model description, stored statically */
        }}
    }}"""
        )
    fmu_load_code = "\n".join(fmu_load_blocks)

    # Generate variable array allocation and population code
    # Real inputs
    real_input_init = _variable_mapping_init_code(
        "inst->real_inputs",
        [v for v in mapping.wrapper_inputs if v.variable_type == "Real"],
        "        ",
    )
    # Integer inputs
    int_input_init = _variable_mapping_init_code(
        "inst->int_inputs",
        [v for v in mapping.wrapper_inputs if v.variable_type == "Integer"],
        "        ",
    )
    # Boolean inputs
    bool_input_init = _variable_mapping_init_code(
        "inst->bool_inputs",
        [v for v in mapping.wrapper_inputs if v.variable_type == "Boolean"],
        "        ",
    )
    # String inputs
    str_input_init = _variable_mapping_init_code(
        "inst->string_inputs",
        [v for v in mapping.wrapper_inputs if v.variable_type == "String"],
        "        ",
    )
    # Real outputs
    real_output_init = _variable_mapping_init_code(
        "inst->real_outputs",
        [v for v in mapping.wrapper_outputs if v.variable_type == "Real"],
        "        ",
    )
    # Integer outputs
    int_output_init = _variable_mapping_init_code(
        "inst->int_outputs",
        [v for v in mapping.wrapper_outputs if v.variable_type == "Integer"],
        "        ",
    )
    # Boolean outputs
    bool_output_init = _variable_mapping_init_code(
        "inst->bool_outputs",
        [v for v in mapping.wrapper_outputs if v.variable_type == "Boolean"],
        "        ",
    )
    # String outputs
    str_output_init = _variable_mapping_init_code(
        "inst->string_outputs",
        [v for v in mapping.wrapper_outputs if v.variable_type == "String"],
        "        ",
    )
    # Real params
    real_param_init = _variable_mapping_init_code(
        "inst->real_params",
        [v for v in mapping.wrapper_parameters if v.variable_type == "Real"],
        "        ",
    )
    # Integer params
    int_param_init = _variable_mapping_init_code(
        "inst->int_params",
        [v for v in mapping.wrapper_parameters if v.variable_type == "Integer"],
        "        ",
    )
    # Boolean params
    bool_param_init = _variable_mapping_init_code(
        "inst->bool_params",
        [v for v in mapping.wrapper_parameters if v.variable_type == "Boolean"],
        "        ",
    )
    # String params
    str_param_init = _variable_mapping_init_code(
        "inst->string_params",
        [v for v in mapping.wrapper_parameters if v.variable_type == "String"],
        "        ",
    )

    # Connections init
    connections_init_lines = []
    for idx, conn in enumerate(mapping.connections):
        connections_init_lines.append(
            f"        inst->connections_src[{idx}].vr = {conn.source_value_reference};"
        )
        connections_init_lines.append(
            f"        inst->connections_src[{idx}].fmu = &inst->internal_fmus[idx_{conn.source_fmu}];"
        )
        connections_init_lines.append(
            f"        inst->connections_tgt[{idx}].vr = {conn.target_value_reference};"
        )
        connections_init_lines.append(
            f"        inst->connections_tgt[{idx}].fmu = &inst->internal_fmus[idx_{conn.target_fmu}];"
        )
    connections_init = "\n".join(connections_init_lines)

    # Do-step input propagation code (by type)
    do_step_input_lines = []
    if all_real_inputs > 0:
        do_step_input_lines.append(
            """        /* Propagate real wrapper inputs to internal FMUs */
        for (int i = 0; i < inst->num_real_inputs; i++) {
            if (inst->real_inputs[i].fmu) {
                InternalFMU* fmu = (InternalFMU*)inst->real_inputs[i].fmu;
                fmi2ValueReference vr = inst->real_inputs[i].vr;
                fmi2Real val = inst->real_inputs[i].value.r;
                fmu->setReal(fmu->component, &vr, 1, &val);
            }
        }"""
        )
    if all_int_inputs > 0:
        do_step_input_lines.append(
            """        /* Propagate integer wrapper inputs to internal FMUs */
        for (int i = 0; i < inst->num_int_inputs; i++) {
            if (inst->int_inputs[i].fmu) {
                InternalFMU* fmu = (InternalFMU*)inst->int_inputs[i].fmu;
                fmi2ValueReference vr = inst->int_inputs[i].vr;
                fmi2Integer val = inst->int_inputs[i].value.i;
                fmu->setInteger(fmu->component, &vr, 1, &val);
            }
        }"""
        )
    if all_bool_inputs > 0:
        do_step_input_lines.append(
            """        /* Propagate boolean wrapper inputs to internal FMUs */
        for (int i = 0; i < inst->num_bool_inputs; i++) {
            if (inst->bool_inputs[i].fmu) {
                InternalFMU* fmu = (InternalFMU*)inst->bool_inputs[i].fmu;
                fmi2ValueReference vr = inst->bool_inputs[i].vr;
                fmi2Boolean val = inst->bool_inputs[i].value.b;
                fmu->setBoolean(fmu->component, &vr, 1, &val);
            }
        }"""
        )
    if all_str_inputs > 0:
        do_step_input_lines.append(
            """        /* Propagate string wrapper inputs to internal FMUs */
        for (int i = 0; i < inst->num_string_inputs; i++) {
            if (inst->string_inputs[i].fmu) {
                InternalFMU* fmu = (InternalFMU*)inst->string_inputs[i].fmu;
                fmi2ValueReference vr = inst->string_inputs[i].vr;
                fmi2String val = inst->string_inputs[i].value.s;
                fmu->setString(fmu->component, &vr, 1, &val);
            }
        }"""
        )
    do_step_input_code = "\n".join(do_step_input_lines)

    # Do-step output propagation code (by type)
    do_step_output_lines = []
    if all_real_outputs > 0:
        do_step_output_lines.append(
            """        /* Update real wrapper outputs from internal FMUs */
        for (int i = 0; i < inst->num_real_outputs; i++) {
            if (inst->real_outputs[i].fmu) {
                InternalFMU* fmu = (InternalFMU*)inst->real_outputs[i].fmu;
                fmi2ValueReference vr = inst->real_outputs[i].vr;
                fmu->getReal(fmu->component, &vr, 1, &inst->real_outputs[i].value.r);
            }
        }"""
        )
    if all_int_outputs > 0:
        do_step_output_lines.append(
            """        /* Update integer wrapper outputs from internal FMUs */
        for (int i = 0; i < inst->num_int_outputs; i++) {
            if (inst->int_outputs[i].fmu) {
                InternalFMU* fmu = (InternalFMU*)inst->int_outputs[i].fmu;
                fmi2ValueReference vr = inst->int_outputs[i].vr;
                fmu->getInteger(fmu->component, &vr, 1, &inst->int_outputs[i].value.i);
            }
        }"""
        )
    if all_bool_outputs > 0:
        do_step_output_lines.append(
            """        /* Update boolean wrapper outputs from internal FMUs */
        for (int i = 0; i < inst->num_bool_outputs; i++) {
            if (inst->bool_outputs[i].fmu) {
                InternalFMU* fmu = (InternalFMU*)inst->bool_outputs[i].fmu;
                fmi2ValueReference vr = inst->bool_outputs[i].vr;
                fmu->getBoolean(fmu->component, &vr, 1, &inst->bool_outputs[i].value.b);
            }
        }"""
        )
    if all_str_outputs > 0:
        do_step_output_lines.append(
            """        /* Update string wrapper outputs from internal FMUs */
        for (int i = 0; i < inst->num_string_outputs; i++) {
            if (inst->string_outputs[i].fmu) {
                InternalFMU* fmu = (InternalFMU*)inst->string_outputs[i].fmu;
                fmi2ValueReference vr = inst->string_outputs[i].vr;
                fmu->getString(fmu->component, &vr, 1, &inst->string_outputs[i].value.s);
            }
        }"""
        )
    do_step_output_code = "\n".join(do_step_output_lines)

    return f"""/**
 * fmi2_interface.c - FMI 2.0 Co-Simulation wrapper implementation.
 *
 * Generated by cs-fmu-packager for: {fmu_name}
 * Internal FMUs: {num_fmus}
 * Wrapper inputs: {num_inputs}, outputs: {num_outputs}, parameters: {num_params}
 * Internal connections: {num_connections}
 */

#include "fmi2_interface.h"
#include "solver_integration.h"
#include "fixed_point_iteration.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <dlfcn.h>
#include <math.h>

/* ---------------------------------------------------------------------------
 * Type definitions for function pointers (from fmi2FunctionTypes.h)
 * --------------------------------------------------------------------------- */
typedef fmi2Component (*fmi2InstantiateME_f)(fmi2String, fmi2Type, fmi2String,
                                              fmi2String, const fmi2CallbackFunctions*,
                                              fmi2Boolean, fmi2Boolean);
typedef void          (*fmi2FreeInstance_f)(fmi2Component);
typedef fmi2Status    (*fmi2SetReal_f)(fmi2Component, const fmi2ValueReference[], size_t, const fmi2Real[]);
typedef fmi2Status    (*fmi2GetReal_f)(fmi2Component, const fmi2ValueReference[], size_t, fmi2Real[]);
typedef fmi2Status    (*fmi2SetInteger_f)(fmi2Component, const fmi2ValueReference[], size_t, const fmi2Integer[]);
typedef fmi2Status    (*fmi2GetInteger_f)(fmi2Component, const fmi2ValueReference[], size_t, fmi2Integer[]);
typedef fmi2Status    (*fmi2SetBoolean_f)(fmi2Component, const fmi2ValueReference[], size_t, const fmi2Boolean[]);
typedef fmi2Status    (*fmi2GetBoolean_f)(fmi2Component, const fmi2ValueReference[], size_t, fmi2Boolean[]);
typedef fmi2Status    (*fmi2SetString_f)(fmi2Component, const fmi2ValueReference[], size_t, const fmi2String[]);
typedef fmi2Status    (*fmi2GetString_f)(fmi2Component, const fmi2ValueReference[], size_t, fmi2String[]);
typedef fmi2Status    (*fmi2SetTime_f)(fmi2Component, fmi2Real);
typedef fmi2Status    (*fmi2SetContinuousStates_f)(fmi2Component, const fmi2Real[], size_t);
typedef fmi2Status    (*fmi2GetDerivatives_f)(fmi2Component, fmi2Real[], size_t);
typedef fmi2Status    (*fmi2GetContinuousStates_f)(fmi2Component, fmi2Real[], size_t);
typedef fmi2Status    (*fmi2EnterInitializationMode_f)(fmi2Component);
typedef fmi2Status    (*fmi2Terminate_f)(fmi2Component);
typedef fmi2Status    (*fmi2SetupExperiment_f)(fmi2Component, fmi2Boolean, fmi2Real, fmi2Real, fmi2Boolean, fmi2Real);

/* ---------------------------------------------------------------------------
 * Struct: WrapperState
 * --------------------------------------------------------------------------- */
typedef enum {{
    WrapperState_Instantiated,
    WrapperState_InitializationMode,
    WrapperState_StepComplete,
    WrapperState_StepInProgress,
    WrapperState_Terminated,
    WrapperState_Error
}} WrapperState;

/* ---------------------------------------------------------------------------
 * Struct: InternalFMU (per internal FMU)
 * --------------------------------------------------------------------------- */
typedef struct {{
    void* libHandle;
    fmi2InstantiateME_f instantiateME;
    fmi2SetReal_f setReal;
    fmi2GetReal_f getReal;
    fmi2GetDerivatives_f getDerivatives;
    fmi2SetTime_f setTime;
    fmi2SetContinuousStates_f setContinuousStates;
    fmi2GetContinuousStates_f getContinuousStates;
    fmi2EnterInitializationMode_f initialize;
    fmi2Terminate_f terminate;
    fmi2FreeInstance_f freeInstance;
    fmi2SetInteger_f setInteger;
    fmi2GetInteger_f getInteger;
    fmi2SetBoolean_f setBoolean;
    fmi2GetBoolean_f getBoolean;
    fmi2SetString_f setString;
    fmi2GetString_f getString;
    int nx;
    fmi2Component component;
    char instance_name[256];
    fmi2Real* state_vector;
}} InternalFMU;

/* ---------------------------------------------------------------------------
 * Struct: VariableMapping
 * --------------------------------------------------------------------------- */
typedef struct {{
    fmi2ValueReference vr;
    union {{
        fmi2Real r;
        fmi2Integer i;
        fmi2Boolean b;
        fmi2String s;
    }} value;
    InternalFMU* fmu;
}} VariableMapping;

/* ---------------------------------------------------------------------------
 * Struct: WrapperInstance (per-instance state)
 * --------------------------------------------------------------------------- */
typedef struct {{
    WrapperState state;
    char instance_name[256];
    const fmi2CallbackFunctions* callbacks;
    fmi2Real current_time;
    fmi2Real communication_step;
    fmi2Real step_size;
    int algebraic_loop_max_iterations;
    double algebraic_loop_tolerance;
    int num_algebraic_loops;

    /* Internal FMU array */
    int num_internal_fmus;
    InternalFMU* internal_fmus;

    /* Real variable mappings */
    int num_real_inputs;
    VariableMapping* real_inputs;
    int num_real_outputs;
    VariableMapping* real_outputs;
    int num_real_params;
    VariableMapping* real_params;

    /* Integer variable mappings */
    int num_int_inputs;
    VariableMapping* int_inputs;
    int num_int_outputs;
    VariableMapping* int_outputs;
    int num_int_params;
    VariableMapping* int_params;

    /* Boolean variable mappings */
    int num_bool_inputs;
    VariableMapping* bool_inputs;
    int num_bool_outputs;
    VariableMapping* bool_outputs;
    int num_bool_params;
    VariableMapping* bool_params;

    /* String variable mappings */
    int num_string_inputs;
    VariableMapping* string_inputs;
    int num_string_outputs;
    VariableMapping* string_outputs;
    int num_string_params;
    VariableMapping* string_params;

    /* Connection routing arrays */
    int num_connections;
    VariableMapping* connections_src;
    VariableMapping* connections_tgt;

    /* Solver state */
    void* arkode_mem;
    void* nv_state;
    double* derivatives;
}} WrapperInstance;

/* ---------------------------------------------------------------------------
 * Internal FMU dynamic loading helpers
 * --------------------------------------------------------------------------- */
#define MAX_RESOURCE_PATH 1024

/* ---------------------------------------------------------------------------
 * Helper: log message through callbacks
 * --------------------------------------------------------------------------- */
static void log_message(WrapperInstance* inst, fmi2Status status, const char* category, const char* msg)
{{
    if (inst && inst->callbacks && inst->callbacks->logger) {{
        inst->callbacks->logger(inst->callbacks->componentEnvironment,
                                inst->instance_name, status, category, msg);
    }}
}}

/* ===========================================================================
 * FMI 2.0 Common Functions
 * =========================================================================== */

FMI2_Export const char* fmi2GetTypesPlatform(void)
{{
    return fmi2TypesPlatform;
}}

FMI2_Export const char* fmi2GetVersion(void)
{{
    return fmi2Version;
}}

FMI2_Export fmi2Status fmi2SetDebugLogging(fmi2Component c, fmi2Boolean loggingOn,
                                            size_t nCategories, const fmi2String categories[])
{{
    if (c == NULL) return fmi2Error;
    WrapperInstance* inst = (WrapperInstance*)c;
    (void)inst; (void)loggingOn; (void)nCategories; (void)categories;
    return fmi2OK;
}}

FMI2_Export fmi2Component fmi2Instantiate(fmi2String instanceName, fmi2Type fmuType,
                                           fmi2String fmuGUID, fmi2String fmuResourceLocation,
                                           const fmi2CallbackFunctions* functions,
                                           fmi2Boolean visible, fmi2Boolean loggingOn)
{{
    if (fmuType != fmi2CoSimulation) {{
        return NULL;
    }}

    if (strcmp(fmuGUID, "{fmu_guid}") != 0) {{
        return NULL;
    }}

    /* Allocate wrapper instance */
    WrapperInstance* inst = (WrapperInstance*)calloc(1, sizeof(WrapperInstance));
    if (inst == NULL) return NULL;

    strncpy(inst->instance_name, instanceName, sizeof(inst->instance_name) - 1);
    inst->state = WrapperState_Instantiated;
    inst->callbacks = functions;
    inst->current_time = 0.0;
    inst->step_size = {spec.solver.step_size};
    inst->communication_step = {spec.wrapper.communication_step};
    inst->algebraic_loop_max_iterations = {spec.solver.algebraic_loop.max_iterations};
    inst->algebraic_loop_tolerance = {spec.solver.algebraic_loop.tolerance};
    inst->num_algebraic_loops = {len(mapping.algebraic_loops)};

    /* Count internal FMU variables */
    inst->num_internal_fmus = {num_fmus};
    inst->internal_fmus = (InternalFMU*)calloc({num_fmus}, sizeof(InternalFMU));
    if (inst->internal_fmus == NULL) {{ free(inst); return NULL; }}

    /* FMU index constants */
{fmu_idx_defs}

    /* Load all internal FMUs */
{fmu_load_code}

    /* Populate FMU index assignments */
{fmu_idx_assigns}

    /* Allocate variable mapping arrays */
    inst->num_real_inputs = {all_real_inputs};
    inst->real_inputs = (VariableMapping*)calloc({all_real_inputs}, sizeof(VariableMapping));
    inst->num_int_inputs = {all_int_inputs};
    inst->int_inputs = (VariableMapping*)calloc({all_int_inputs}, sizeof(VariableMapping));
    inst->num_bool_inputs = {all_bool_inputs};
    inst->bool_inputs = (VariableMapping*)calloc({all_bool_inputs}, sizeof(VariableMapping));
    inst->num_string_inputs = {all_str_inputs};
    inst->string_inputs = (VariableMapping*)calloc({all_str_inputs}, sizeof(VariableMapping));

    inst->num_real_outputs = {all_real_outputs};
    inst->real_outputs = (VariableMapping*)calloc({all_real_outputs}, sizeof(VariableMapping));
    inst->num_int_outputs = {all_int_outputs};
    inst->int_outputs = (VariableMapping*)calloc({all_int_outputs}, sizeof(VariableMapping));
    inst->num_bool_outputs = {all_bool_outputs};
    inst->bool_outputs = (VariableMapping*)calloc({all_bool_outputs}, sizeof(VariableMapping));
    inst->num_string_outputs = {all_str_outputs};
    inst->string_outputs = (VariableMapping*)calloc({all_str_outputs}, sizeof(VariableMapping));

    inst->num_real_params = {all_real_params};
    inst->real_params = (VariableMapping*)calloc({all_real_params}, sizeof(VariableMapping));
    inst->num_int_params = {all_int_params};
    inst->int_params = (VariableMapping*)calloc({all_int_params}, sizeof(VariableMapping));
    inst->num_bool_params = {all_bool_params};
    inst->bool_params = (VariableMapping*)calloc({all_bool_params}, sizeof(VariableMapping));
    inst->num_string_params = {all_str_params};
    inst->string_params = (VariableMapping*)calloc({all_str_params}, sizeof(VariableMapping));

    inst->num_connections = {num_connections};
    inst->connections_src = (VariableMapping*)calloc({num_connections}, sizeof(VariableMapping));
    inst->connections_tgt = (VariableMapping*)calloc({num_connections}, sizeof(VariableMapping));

    /* Populate variable mapping arrays */
    if ({all_real_inputs} > 0) {{
{real_input_init}
    }}
    if ({all_int_inputs} > 0) {{
{int_input_init}
    }}
    if ({all_bool_inputs} > 0) {{
{bool_input_init}
    }}
    if ({all_str_inputs} > 0) {{
{str_input_init}
    }}
    if ({all_real_outputs} > 0) {{
{real_output_init}
    }}
    if ({all_int_outputs} > 0) {{
{int_output_init}
    }}
    if ({all_bool_outputs} > 0) {{
{bool_output_init}
    }}
    if ({all_str_outputs} > 0) {{
{str_output_init}
    }}
    if ({all_real_params} > 0) {{
{real_param_init}
    }}
    if ({all_int_params} > 0) {{
{int_param_init}
    }}
    if ({all_bool_params} > 0) {{
{bool_param_init}
    }}
    if ({all_str_params} > 0) {{
{str_param_init}
    }}

    /* Populate connection routing arrays */
    if ({num_connections} > 0) {{
{connections_init}
    }}

    log_message(inst, fmi2OK, "init", "Wrapper instance created successfully");
    return (fmi2Component)inst;
}}

FMI2_Export void fmi2FreeInstance(fmi2Component c)
{{
    if (c == NULL) return;
    WrapperInstance* inst = (WrapperInstance*)c;

    /* Free internal FMUs */
    if (inst->internal_fmus) {{
        for (int i = 0; i < inst->num_internal_fmus; i++) {{
            InternalFMU* fmu = &inst->internal_fmus[i];
            if (fmu->component && fmu->freeInstance) {{
                fmu->freeInstance(fmu->component);
            }}
            if (fmu->libHandle) {{
                dlclose(fmu->libHandle);
            }}
            free(fmu->state_vector);
        }}
        free(inst->internal_fmus);
    }}

    /* Free variable mappings */
    free(inst->real_inputs);
    free(inst->int_inputs);
    free(inst->bool_inputs);
    free(inst->string_inputs);
    free(inst->real_outputs);
    free(inst->int_outputs);
    free(inst->bool_outputs);
    free(inst->string_outputs);
    free(inst->real_params);
    free(inst->int_params);
    free(inst->bool_params);
    free(inst->string_params);
    free(inst->connections_src);
    free(inst->connections_tgt);

    solver_free(inst);
    free(inst);
}}

FMI2_Export fmi2Status fmi2SetupExperiment(fmi2Component c, fmi2Boolean toleranceDefined,
                                            fmi2Real tolerance, fmi2Real startTime,
                                            fmi2Boolean stopTimeDefined, fmi2Real stopTime)
{{
    if (c == NULL) return fmi2Error;
    WrapperInstance* inst = (WrapperInstance*)c;
    if (inst->state != WrapperState_Instantiated) return fmi2Error;

    inst->current_time = startTime;
    return fmi2OK;
}}

FMI2_Export fmi2Status fmi2EnterInitializationMode(fmi2Component c)
{{
    if (c == NULL) return fmi2Error;
    WrapperInstance* inst = (WrapperInstance*)c;
    if (inst->state != WrapperState_Instantiated) return fmi2Error;
    inst->state = WrapperState_InitializationMode;
    return fmi2OK;
}}

FMI2_Export fmi2Status fmi2ExitInitializationMode(fmi2Component c)
{{
    if (c == NULL) return fmi2Error;
    WrapperInstance* inst = (WrapperInstance*)c;
    if (inst->state != WrapperState_InitializationMode) return fmi2Error;

    /* Initialize solver */
    if (solver_init(inst) != 0) {{
        log_message(inst, fmi2Error, "solver", "Failed to initialize solver");
        inst->state = WrapperState_Error;
        return fmi2Error;
    }}

    inst->state = WrapperState_StepComplete;
    return fmi2OK;
}}

FMI2_Export fmi2Status fmi2Terminate(fmi2Component c)
{{
    if (c == NULL) return fmi2Error;
    WrapperInstance* inst = (WrapperInstance*)c;
    inst->state = WrapperState_Terminated;
    return fmi2OK;
}}

FMI2_Export fmi2Status fmi2Reset(fmi2Component c)
{{
    if (c == NULL) return fmi2Error;
    WrapperInstance* inst = (WrapperInstance*)c;
    inst->current_time = 0.0;
    inst->state = WrapperState_Instantiated;
    return fmi2OK;
}}

/* ===========================================================================
 * Variable getter/setter functions
 * =========================================================================== */

FMI2_Export fmi2Status fmi2GetReal(fmi2Component c, const fmi2ValueReference vr[], size_t nvr, fmi2Real value[])
{{
    if (c == NULL) return fmi2Error;
    WrapperInstance* inst = (WrapperInstance*)c;

    for (size_t i = 0; i < nvr; i++) {{
        value[i] = 0.0;

        /* Check wrapper outputs */
        for (int j = 0; j < inst->num_real_outputs; j++) {{
            if (inst->real_outputs[j].vr == vr[i]) {{
                value[i] = inst->real_outputs[j].value.r;
                break;
            }}
        }}
    }}

    return fmi2OK;
}}

FMI2_Export fmi2Status fmi2SetReal(fmi2Component c, const fmi2ValueReference vr[], size_t nvr, const fmi2Real value[])
{{
    if (c == NULL) return fmi2Error;
    WrapperInstance* inst = (WrapperInstance*)c;

    for (size_t i = 0; i < nvr; i++) {{
        /* Check wrapper inputs */
        int found = 0;
        for (int j = 0; j < inst->num_real_inputs; j++) {{
            if (inst->real_inputs[j].vr == vr[i]) {{
                inst->real_inputs[j].value.r = value[i];
                found = 1;

                /* Propagate to internal FMU if connected */
                if (inst->real_inputs[j].fmu) {{
                    InternalFMU* fmu = (InternalFMU*)inst->real_inputs[j].fmu;
                    fmi2ValueReference tgt_vr = inst->real_inputs[j].vr;
                    fmu->setReal(fmu->component, &tgt_vr, 1, &value[i]);
                }}
                break;
            }}
        }}

        /* Check wrapper parameters */
        if (!found) {{
            for (int j = 0; j < inst->num_real_params; j++) {{
                if (inst->real_params[j].vr == vr[i]) {{
                    inst->real_params[j].value.r = value[i];
                    if (inst->real_params[j].fmu) {{
                        InternalFMU* fmu = (InternalFMU*)inst->real_params[j].fmu;
                        fmi2ValueReference tgt_vr = inst->real_params[j].vr;
                        fmu->setReal(fmu->component, &tgt_vr, 1, &value[i]);
                    }}
                    found = 1;
                    break;
                }}
            }}
        }}
    }}

    return fmi2OK;
}}

FMI2_Export fmi2Status fmi2GetInteger(fmi2Component c, const fmi2ValueReference vr[], size_t nvr, fmi2Integer value[])
{{
    if (c == NULL) return fmi2Error;
    WrapperInstance* inst = (WrapperInstance*)c;

    for (size_t i = 0; i < nvr; i++) {{
        value[i] = 0;

        /* Check wrapper outputs */
        for (int j = 0; j < inst->num_int_outputs; j++) {{
            if (inst->int_outputs[j].vr == vr[i]) {{
                value[i] = inst->int_outputs[j].value.i;
                break;
            }}
        }}
    }}

    return fmi2OK;
}}

FMI2_Export fmi2Status fmi2GetBoolean(fmi2Component c, const fmi2ValueReference vr[], size_t nvr, fmi2Boolean value[])
{{
    if (c == NULL) return fmi2Error;
    WrapperInstance* inst = (WrapperInstance*)c;

    for (size_t i = 0; i < nvr; i++) {{
        value[i] = fmi2False;

        /* Check wrapper outputs */
        for (int j = 0; j < inst->num_bool_outputs; j++) {{
            if (inst->bool_outputs[j].vr == vr[i]) {{
                value[i] = inst->bool_outputs[j].value.b;
                break;
            }}
        }}
    }}

    return fmi2OK;
}}

FMI2_Export fmi2Status fmi2GetString(fmi2Component c, const fmi2ValueReference vr[], size_t nvr, fmi2String value[])
{{
    if (c == NULL) return fmi2Error;
    WrapperInstance* inst = (WrapperInstance*)c;

    for (size_t i = 0; i < nvr; i++) {{
        value[i] = "";

        /* Check wrapper outputs */
        for (int j = 0; j < inst->num_string_outputs; j++) {{
            if (inst->string_outputs[j].vr == vr[i]) {{
                value[i] = inst->string_outputs[j].value.s;
                break;
            }}
        }}
    }}

    return fmi2OK;
}}

FMI2_Export fmi2Status fmi2SetInteger(fmi2Component c, const fmi2ValueReference vr[], size_t nvr, const fmi2Integer value[])
{{
    if (c == NULL) return fmi2Error;
    WrapperInstance* inst = (WrapperInstance*)c;

    for (size_t i = 0; i < nvr; i++) {{
        int found = 0;
        for (int j = 0; j < inst->num_int_inputs; j++) {{
            if (inst->int_inputs[j].vr == vr[i]) {{
                inst->int_inputs[j].value.i = value[i];
                found = 1;
                if (inst->int_inputs[j].fmu) {{
                    InternalFMU* fmu = (InternalFMU*)inst->int_inputs[j].fmu;
                    fmi2ValueReference tgt_vr = inst->int_inputs[j].vr;
                    fmu->setInteger(fmu->component, &tgt_vr, 1, &value[i]);
                }}
                break;
            }}
        }}

        if (!found) {{
            for (int j = 0; j < inst->num_int_params; j++) {{
                if (inst->int_params[j].vr == vr[i]) {{
                    inst->int_params[j].value.i = value[i];
                    if (inst->int_params[j].fmu) {{
                        InternalFMU* fmu = (InternalFMU*)inst->int_params[j].fmu;
                        fmi2ValueReference tgt_vr = inst->int_params[j].vr;
                        fmu->setInteger(fmu->component, &tgt_vr, 1, &value[i]);
                    }}
                    found = 1;
                    break;
                }}
            }}
        }}
    }}

    return fmi2OK;
}}

FMI2_Export fmi2Status fmi2SetBoolean(fmi2Component c, const fmi2ValueReference vr[], size_t nvr, const fmi2Boolean value[])
{{
    if (c == NULL) return fmi2Error;
    WrapperInstance* inst = (WrapperInstance*)c;

    for (size_t i = 0; i < nvr; i++) {{
        int found = 0;
        for (int j = 0; j < inst->num_bool_inputs; j++) {{
            if (inst->bool_inputs[j].vr == vr[i]) {{
                inst->bool_inputs[j].value.b = value[i];
                found = 1;
                if (inst->bool_inputs[j].fmu) {{
                    InternalFMU* fmu = (InternalFMU*)inst->bool_inputs[j].fmu;
                    fmi2ValueReference tgt_vr = inst->bool_inputs[j].vr;
                    fmu->setBoolean(fmu->component, &tgt_vr, 1, &value[i]);
                }}
                break;
            }}
        }}

        if (!found) {{
            for (int j = 0; j < inst->num_bool_params; j++) {{
                if (inst->bool_params[j].vr == vr[i]) {{
                    inst->bool_params[j].value.b = value[i];
                    if (inst->bool_params[j].fmu) {{
                        InternalFMU* fmu = (InternalFMU*)inst->bool_params[j].fmu;
                        fmi2ValueReference tgt_vr = inst->bool_params[j].vr;
                        fmu->setBoolean(fmu->component, &tgt_vr, 1, &value[i]);
                    }}
                    found = 1;
                    break;
                }}
            }}
        }}
    }}

    return fmi2OK;
}}

FMI2_Export fmi2Status fmi2SetString(fmi2Component c, const fmi2ValueReference vr[], size_t nvr, const fmi2String value[])
{{
    if (c == NULL) return fmi2Error;
    WrapperInstance* inst = (WrapperInstance*)c;

    for (size_t i = 0; i < nvr; i++) {{
        int found = 0;
        for (int j = 0; j < inst->num_string_inputs; j++) {{
            if (inst->string_inputs[j].vr == vr[i]) {{
                /* Free old value and allocate new one */
                if (inst->string_inputs[j].value.s) {{
                    free((void*)inst->string_inputs[j].value.s);
                }}
                inst->string_inputs[j].value.s = strdup(value[i]);
                found = 1;
                if (inst->string_inputs[j].fmu) {{
                    InternalFMU* fmu = (InternalFMU*)inst->string_inputs[j].fmu;
                    fmi2ValueReference tgt_vr = inst->string_inputs[j].vr;
                    fmu->setString(fmu->component, &tgt_vr, 1, &value[i]);
                }}
                break;
            }}
        }}

        if (!found) {{
            for (int j = 0; j < inst->num_string_params; j++) {{
                if (inst->string_params[j].vr == vr[i]) {{
                    if (inst->string_params[j].value.s) {{
                        free((void*)inst->string_params[j].value.s);
                    }}
                    inst->string_params[j].value.s = strdup(value[i]);
                    if (inst->string_params[j].fmu) {{
                        InternalFMU* fmu = (InternalFMU*)inst->string_params[j].fmu;
                        fmi2ValueReference tgt_vr = inst->string_params[j].vr;
                        fmu->setString(fmu->component, &tgt_vr, 1, &value[i]);
                    }}
                    found = 1;
                    break;
                }}
            }}
        }}
    }}

    return fmi2OK;
}}

/* ===========================================================================
 * FMU state functions (not supported in v1)
 * =========================================================================== */

FMI2_Export fmi2Status fmi2GetFMUstate(fmi2Component c, fmi2FMUstate* FMUstate)
{{ (void)c; (void)FMUstate; return fmi2Discard; }}
FMI2_Export fmi2Status fmi2SetFMUstate(fmi2Component c, fmi2FMUstate FMUstate)
{{ (void)c; (void)FMUstate; return fmi2Discard; }}
FMI2_Export fmi2Status fmi2FreeFMUstate(fmi2Component c, fmi2FMUstate* FMUstate)
{{ (void)c; (void)FMUstate; return fmi2Discard; }}
FMI2_Export fmi2Status fmi2SerializedFMUstateSize(fmi2Component c, fmi2FMUstate FMUstate, size_t* size)
{{ (void)c; (void)FMUstate; (void)size; return fmi2Discard; }}
FMI2_Export fmi2Status fmi2SerializeFMUstate(fmi2Component c, fmi2FMUstate FMUstate, fmi2Byte serializedState[], size_t size)
{{ (void)c; (void)FMUstate; (void)serializedState; (void)size; return fmi2Discard; }}
FMI2_Export fmi2Status fmi2DeSerializeFMUstate(fmi2Component c, const fmi2Byte serializedState[], size_t size, fmi2FMUstate* FMUstate)
{{ (void)c; (void)serializedState; (void)size; (void)FMUstate; return fmi2Discard; }}

FMI2_Export fmi2Status fmi2GetDirectionalDerivative(fmi2Component c,
    const fmi2ValueReference vUnknown_ref[], size_t nUnknown,
    const fmi2ValueReference vKnown_ref[], size_t nKnown,
    const fmi2Real dvKnown[], fmi2Real dvUnknown[])
{{
    (void)c; (void)vUnknown_ref; (void)nUnknown;
    (void)vKnown_ref; (void)nKnown; (void)dvKnown; (void)dvUnknown;
    return fmi2Discard;
}}

/* ===========================================================================
 * FMI 2.0 Co-Simulation specific functions
 * =========================================================================== */

FMI2_Export fmi2Status fmi2SetRealInputDerivatives(fmi2Component c,
    const fmi2ValueReference vr[], size_t nvr,
    const fmi2Integer order[], const fmi2Real value[])
{{
    (void)c; (void)vr; (void)nvr; (void)order; (void)value;
    return fmi2Discard;
}}

FMI2_Export fmi2Status fmi2GetRealOutputDerivatives(fmi2Component c,
    const fmi2ValueReference vr[], size_t nvr,
    const fmi2Integer order[], fmi2Real value[])
{{
    (void)c; (void)vr; (void)nvr; (void)order; (void)value;
    return fmi2Discard;
}}

FMI2_Export fmi2Status fmi2DoStep(fmi2Component c,
                                   fmi2Real currentCommunicationPoint,
                                   fmi2Real communicationStepSize,
                                   fmi2Boolean noSetFMUStatePriorToCurrentPoint)
{{
    if (c == NULL) return fmi2Error;
    WrapperInstance* inst = (WrapperInstance*)c;
    if (inst->state != WrapperState_StepComplete) return fmi2Error;

    inst->state = WrapperState_StepInProgress;
    inst->current_time = currentCommunicationPoint;

    /* Step 1: Resolve algebraic loops (fixed-point iteration) */
    int fp_result = fixed_point_resolve_all(inst, currentCommunicationPoint);
    if (fp_result < 0) {{
        log_message(inst, fmi2Error, "solver", "Fixed-point iteration failed");
        inst->state = WrapperState_Error;
        return fmi2Error;
    }}

    /* Step 2: Perform internal integration sub-steps */
    double t_end = currentCommunicationPoint + communicationStepSize;
    double t = currentCommunicationPoint;

    while (t < t_end) {{
        double h = (t + inst->step_size <= t_end) ? inst->step_size : (t_end - t);
        if (h < 1e-15) break;

        /* Update input variables on internal FMUs from wrapper inputs */
{do_step_input_code}

        /* Propagate internal connections */
        for (int c_idx = 0; c_idx < inst->num_connections; c_idx++) {{
            InternalFMU* src_fmu = (InternalFMU*)inst->connections_src[c_idx].fmu;
            InternalFMU* tgt_fmu = (InternalFMU*)inst->connections_tgt[c_idx].fmu;
            if (src_fmu && tgt_fmu) {{
                double src_val = 0.0;
                fmi2ValueReference src_vr = inst->connections_src[c_idx].vr;
                fmi2ValueReference tgt_vr = inst->connections_tgt[c_idx].vr;
                src_fmu->getReal(src_fmu->component, &src_vr, 1, &src_val);
                tgt_fmu->setReal(tgt_fmu->component, &tgt_vr, 1, &src_val);
            }}
        }}

        /* Perform integration sub-step */
        int result = solver_step(inst, t, h);
        if (result != 0) {{
            log_message(inst, fmi2Error, "solver", "Solver step failed at t=%g", t);
            inst->state = WrapperState_Error;
            return fmi2Error;
        }}

        t += h;
    }}

    /* Step 3: Update wrapper outputs from internal FMUs */
{do_step_output_code}

    inst->current_time = t_end;
    inst->state = WrapperState_StepComplete;
    return fmi2OK;
}}

FMI2_Export fmi2Status fmi2CancelStep(fmi2Component c)
{{
    (void)c;
    return fmi2OK;
}}

/* ===========================================================================
 * Status inquiry functions
 * =========================================================================== */

FMI2_Export fmi2Status fmi2GetStatus(fmi2Component c, const fmi2StatusKind s, fmi2Status* value)
{{
    (void)c;
    switch (s) {{
        case fmi2DoStepStatus:
            *value = fmi2OK;
            break;
        case fmi2PendingStatus:
            *value = fmi2Discard;
            break;
        case fmi2LastSuccessfulTime:
            *value = fmi2Discard;
            break;
        case fmi2Terminated:
            *value = fmi2Discard;
            break;
    }}
    return fmi2OK;
}}

FMI2_Export fmi2Status fmi2GetRealStatus(fmi2Component c, const fmi2StatusKind s, fmi2Real* value)
{{
    if (c == NULL) return fmi2Error;
    WrapperInstance* inst = (WrapperInstance*)c;
    if (s == fmi2LastSuccessfulTime) {{
        *value = inst->current_time;
        return fmi2OK;
    }}
    return fmi2Discard;
}}

FMI2_Export fmi2Status fmi2GetIntegerStatus(fmi2Component c, const fmi2StatusKind s, fmi2Integer* value)
{{
    (void)c; (void)s; (void)value;
    return fmi2Discard;
}}

FMI2_Export fmi2Status fmi2GetBooleanStatus(fmi2Component c, const fmi2StatusKind s, fmi2Boolean* value)
{{
    (void)c; (void)s; (void)value;
    return fmi2Discard;
}}

FMI2_Export fmi2Status fmi2GetStringStatus(fmi2Component c, const fmi2StatusKind s, fmi2String* value)
{{
    (void)c; (void)s; (void)value;
    return fmi2Discard;
}}
"""