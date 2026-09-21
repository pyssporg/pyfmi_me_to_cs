/* fmi2_interface.h - Shared type declarations for the generated wrapper.
 *
 * Included by fmi2_interface.c, solver_integration.c and
 * fixed_point_iteration.c so that all translation units agree on the
 * function-pointer types, internal FMU state and wrapper instance layout.
 */

#ifndef FMI2_INTERFACE_H
#define FMI2_INTERFACE_H

#include "fmi2Functions.h"

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
typedef fmi2Status    (*fmi2ExitInitializationMode_f)(fmi2Component);
typedef fmi2Status    (*fmi2Terminate_f)(fmi2Component);
typedef fmi2Status    (*fmi2SetupExperiment_f)(fmi2Component, fmi2Boolean, fmi2Real, fmi2Real, fmi2Boolean, fmi2Real);

/* ---------------------------------------------------------------------------
 * Struct: WrapperState
 * --------------------------------------------------------------------------- */
typedef enum {
    WrapperState_Instantiated,
    WrapperState_InitializationMode,
    WrapperState_StepComplete,
    WrapperState_StepInProgress,
    WrapperState_Terminated,
    WrapperState_Error
} WrapperState;

/* ---------------------------------------------------------------------------
 * Struct: InternalFMU (per internal FMU)
 * --------------------------------------------------------------------------- */
typedef struct {
    void* libHandle;
    fmi2InstantiateME_f instantiateME;
    fmi2SetReal_f setReal;
    fmi2GetReal_f getReal;
    fmi2GetDerivatives_f getDerivatives;
    fmi2SetTime_f setTime;
    fmi2SetContinuousStates_f setContinuousStates;
    fmi2GetContinuousStates_f getContinuousStates;
    fmi2EnterInitializationMode_f initialize;
    fmi2ExitInitializationMode_f exitInitialize;
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
} InternalFMU;

/* ---------------------------------------------------------------------------
 * Struct: VariableMapping
 * --------------------------------------------------------------------------- */
typedef struct {
    fmi2ValueReference vr;          /* wrapper boundary value reference */
    fmi2ValueReference internal_vr; /* value reference inside internal FMU */
    union {
        fmi2Real r;
        fmi2Integer i;
        fmi2Boolean b;
        fmi2String s;
    } value;
    InternalFMU* fmu;
} VariableMapping;

/* ---------------------------------------------------------------------------
 * Struct: WrapperInstance (per-instance state)
 * --------------------------------------------------------------------------- */
typedef struct {
    WrapperState state;
    char instance_name[256];
    const fmi2CallbackFunctions* callbacks;
    fmi2Real current_time;
    fmi2Real communication_step;
    fmi2Real step_size;
    int solver_type;  /* 0 = fixed_step, 1 = variable_step */
    double solver_tolerance;
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
    void* sunctx;
} WrapperInstance;

#define MAX_RESOURCE_PATH 1024

#endif /* FMI2_INTERFACE_H */