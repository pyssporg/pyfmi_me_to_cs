"""Generate fmi2_interface.c - the main FMI 2.0 CS implementation."""
from __future__ import annotations

from cs_fmu_packager.models import (
    MappedVariable,
    MappingTable,
    PackageSpec,
    SOLVER_STEP_SIZE_PARAM,
    SOLVER_TOLERANCE_PARAM,
    SOLVER_TYPE_ENUM,
    SOLVER_TYPE_PARAM,
)
from cs_fmu_packager.model_description import _derive_guid


def _continuous_states(doc) -> int:
    """Count continuous-time states of an internal FMU.

    Prefer the model description's ``ModelStructure/Derivatives`` list (the
    authoritative count); fall back to counting ``local``/``continuous``
    variables while excluding ``der(...)`` helper variables.
    """
    ms = getattr(doc, "model_structure", None)
    if ms is not None:
        derivatives = getattr(ms, "derivatives", None)
        if derivatives:
            return len(derivatives)
    n = 0
    for v in doc.variables:
        causality = v.causality or "local"
        variability = v.variability or (
            "parameter" if causality == "parameter" else "continuous"
        )
        if (
            causality == "local"
            and variability == "continuous"
            and not v.name.startswith("der(")
        ):
            n += 1
    return n


def _variable_mapping_init_code(
    varname: str,
    vars_list: list[MappedVariable],
    indent: str,
    fmu_index: dict,
) -> str:
    """Generate C init code that populates a VariableMapping array."""
    lines: list[str] = []
    for idx, var in enumerate(vars_list):
        fmu_ptr = "NULL"
        if var.causality == "input" or var.causality == "parameter":
            if var.target_fmu is not None:
                fmu_ptr = f"&inst->internal_fmus[{fmu_index[var.target_fmu]}]"
        elif var.causality == "output":
            if var.source_fmu is not None:
                fmu_ptr = f"&inst->internal_fmus[{fmu_index[var.source_fmu]}]"

        boundary_vr = (
            var.wrapper_value_reference
            if var.wrapper_value_reference is not None else idx + 1
        )
        internal_vr = (
            var.target_value_reference
            if var.causality in ("input", "parameter")
            else var.source_value_reference
        ) or 0
        lines.append(f"{indent}{varname}[{idx}].vr = {boundary_vr};")
        lines.append(f"{indent}{varname}[{idx}].internal_vr = {internal_vr};")
        lines.append(f"{indent}{varname}[{idx}].fmu = {fmu_ptr};")

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
    fmu_guid = _derive_guid(spec)
    num_fmus = len(spec.fmus)
    num_inputs = len(mapping.wrapper_inputs)
    num_outputs = len(mapping.wrapper_outputs)
    all_params = mapping.wrapper_parameters + mapping.reserved_parameters
    num_params = len(all_params)
    num_connections = len(mapping.connections)

    # Type×role combinations for consolidation (IMP-020, IMP-021)
    _type_role_combos = [
        ("real", "Real",   "input",    "input",  mapping.wrapper_inputs),
        ("int",  "Integer","input",    "input",  mapping.wrapper_inputs),
        ("bool", "Boolean","input",    "input",  mapping.wrapper_inputs),
        ("str",  "String", "input",    "input",  mapping.wrapper_inputs),
        ("real", "Real",   "output",   "output", mapping.wrapper_outputs),
        ("int",  "Integer","output",   "output", mapping.wrapper_outputs),
        ("bool", "Boolean","output",   "output", mapping.wrapper_outputs),
        ("str",  "String", "output",   "output", mapping.wrapper_outputs),
        ("real", "Real",   "parameter","param",  all_params),
        ("int",  "Integer","parameter","param",  all_params),
        ("bool", "Boolean","parameter","param",  all_params),
        ("str",  "String", "parameter","param",  all_params),
    ]

    _counts = {}
    for ts, vt, caus, rs, vl in _type_role_combos:
        _counts[f"all_{ts}_{rs}s"] = len(
            [v for v in vl if v.causality == caus and v.variable_type == vt]
        )
    all_real_inputs  = _counts["all_real_inputs"]
    all_int_inputs   = _counts["all_int_inputs"]
    all_bool_inputs  = _counts["all_bool_inputs"]
    all_str_inputs   = _counts["all_str_inputs"]
    all_real_outputs = _counts["all_real_outputs"]
    all_int_outputs  = _counts["all_int_outputs"]
    all_bool_outputs = _counts["all_bool_outputs"]
    all_str_outputs  = _counts["all_str_outputs"]
    all_real_params  = _counts["all_real_params"]
    all_int_params   = _counts["all_int_params"]
    all_bool_params  = _counts["all_bool_params"]
    all_str_params   = _counts["all_str_params"]

    # Map FMU ids to their position in the internal_fmus array (IMP-028:
    # the per-FMU idx_* aliases leaked out of fmi2Instantiate, so generated
    # code could not compile; emit literal indices instead).
    fmu_index = {fmu_id: idx for idx, fmu_id in enumerate(spec.fmus)}

    # Build FMU loading code
    fmu_load_blocks = []
    for idx, (fmu_id, fmu_ref) in enumerate(spec.fmus.items()):
        caps = mapping.fmus[fmu_id].capabilities
        model_identifier = (caps.model_identifier if caps else None) or fmu_id
        fmu_doc = mapping.fmus.get(fmu_id)
        internal_guid = fmu_doc.guid if fmu_doc is not None else "default-guid"
        nnx = _continuous_states(fmu_doc) if fmu_doc is not None else 0
        fmu_load_blocks.append(
            f"""    /* Load FMU: {fmu_id} */
    {{
        InternalFMU* fmu = &inst->internal_fmus[{idx}];
        fmu->nx = {nnx};  /* continuous states from model description */
        strncpy(fmu->instance_name, "{fmu_id}", sizeof(fmu->instance_name) - 1);

        /* Build path to the FMU shared library.  Masters may pass the FMU
         * root or its resources/ directory, and per FMI as a file:// URI
         * which dlopen cannot use, so normalise to a plain root first.
         * Internal FMU binaries live under resources/<id>/binaries/. */
        char res_root[MAX_RESOURCE_PATH];
        {{
            const char* src = (fmuResourceLocation != NULL) ? fmuResourceLocation : "";
            if (strncmp(src, "file://", 7) == 0) src += 7;
            size_t n = strlen(src);
            while (n > 0 && src[n - 1] == '/') n--;
            if (n >= 10 && strncmp(src + n - 10, "/resources", 10) == 0) n -= 10;
            while (n > 0 && src[n - 1] == '/') n--;
            if (n >= sizeof(res_root)) n = sizeof(res_root) - 1;
            strncpy(res_root, src, n);
            res_root[n] = '\\0';
        }}

        char lib_path[MAX_RESOURCE_PATH];
        if (res_root[0] == '\\0') {{
            snprintf(lib_path, sizeof(lib_path), "resources/%s/binaries/linux64/{model_identifier}.so",
                     "{fmu_id}");
        }} else {{
            snprintf(lib_path, sizeof(lib_path), "%s/resources/%s/binaries/linux64/{model_identifier}.so",
                     res_root, "{fmu_id}");
        }}

        fmu->libHandle = dlopen(lib_path, RTLD_NOW | RTLD_LOCAL);
        if (fmu->libHandle == NULL) {{
            log_message(inst, fmi2Error, "init",
                        "Failed to dlopen internal FMU '%s' (%s): %s", "{fmu_id}", lib_path, dlerror());
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
            fmu->instantiateME = (fmi2InstantiateME_f)dlsym(fmu->libHandle, "{model_identifier}_fmi2Instantiate");
        }}
        fmu->setReal = (fmi2SetReal_f)dlsym(fmu->libHandle, "fmi2SetReal");
        if (fmu->setReal == NULL) fmu->setReal = (fmi2SetReal_f)dlsym(fmu->libHandle, "{model_identifier}_fmi2SetReal");
        fmu->getReal = (fmi2GetReal_f)dlsym(fmu->libHandle, "fmi2GetReal");
        if (fmu->getReal == NULL) fmu->getReal = (fmi2GetReal_f)dlsym(fmu->libHandle, "{model_identifier}_fmi2GetReal");
        fmu->getDerivatives = (fmi2GetDerivatives_f)dlsym(fmu->libHandle, "fmi2GetDerivatives");
        if (fmu->getDerivatives == NULL) fmu->getDerivatives = (fmi2GetDerivatives_f)dlsym(fmu->libHandle, "{model_identifier}_fmi2GetDerivatives");
        fmu->setTime = (fmi2SetTime_f)dlsym(fmu->libHandle, "fmi2SetTime");
        if (fmu->setTime == NULL) fmu->setTime = (fmi2SetTime_f)dlsym(fmu->libHandle, "{model_identifier}_fmi2SetTime");
        fmu->setContinuousStates = (fmi2SetContinuousStates_f)dlsym(fmu->libHandle, "fmi2SetContinuousStates");
        if (fmu->setContinuousStates == NULL) fmu->setContinuousStates = (fmi2SetContinuousStates_f)dlsym(fmu->libHandle, "{model_identifier}_fmi2SetContinuousStates");
        fmu->getContinuousStates = (fmi2GetContinuousStates_f)dlsym(fmu->libHandle, "fmi2GetContinuousStates");
        if (fmu->getContinuousStates == NULL) fmu->getContinuousStates = (fmi2GetContinuousStates_f)dlsym(fmu->libHandle, "{model_identifier}_fmi2GetContinuousStates");
        fmu->initialize = (fmi2EnterInitializationMode_f)dlsym(fmu->libHandle, "fmi2EnterInitializationMode");
        if (fmu->initialize == NULL) fmu->initialize = (fmi2EnterInitializationMode_f)dlsym(fmu->libHandle, "{model_identifier}_fmi2EnterInitializationMode");
        fmu->exitInitialize = (fmi2ExitInitializationMode_f)dlsym(fmu->libHandle, "fmi2ExitInitializationMode");
        if (fmu->exitInitialize == NULL) fmu->exitInitialize = (fmi2ExitInitializationMode_f)dlsym(fmu->libHandle, "{model_identifier}_fmi2ExitInitializationMode");
        fmu->terminate = (fmi2Terminate_f)dlsym(fmu->libHandle, "fmi2Terminate");
        if (fmu->terminate == NULL) fmu->terminate = (fmi2Terminate_f)dlsym(fmu->libHandle, "{model_identifier}_fmi2Terminate");
        fmu->freeInstance = (fmi2FreeInstance_f)dlsym(fmu->libHandle, "fmi2FreeInstance");
        if (fmu->freeInstance == NULL) fmu->freeInstance = (fmi2FreeInstance_f)dlsym(fmu->libHandle, "{model_identifier}_fmi2FreeInstance");
        fmu->setInteger = (fmi2SetInteger_f)dlsym(fmu->libHandle, "fmi2SetInteger");
        if (fmu->setInteger == NULL) fmu->setInteger = (fmi2SetInteger_f)dlsym(fmu->libHandle, "{model_identifier}_fmi2SetInteger");
        fmu->getInteger = (fmi2GetInteger_f)dlsym(fmu->libHandle, "fmi2GetInteger");
        if (fmu->getInteger == NULL) fmu->getInteger = (fmi2GetInteger_f)dlsym(fmu->libHandle, "{model_identifier}_fmi2GetInteger");
        fmu->setBoolean = (fmi2SetBoolean_f)dlsym(fmu->libHandle, "fmi2SetBoolean");
        if (fmu->setBoolean == NULL) fmu->setBoolean = (fmi2SetBoolean_f)dlsym(fmu->libHandle, "{model_identifier}_fmi2SetBoolean");
        fmu->getBoolean = (fmi2GetBoolean_f)dlsym(fmu->libHandle, "fmi2GetBoolean");
        if (fmu->getBoolean == NULL) fmu->getBoolean = (fmi2GetBoolean_f)dlsym(fmu->libHandle, "{model_identifier}_fmi2GetBoolean");
        fmu->setString = (fmi2SetString_f)dlsym(fmu->libHandle, "fmi2SetString");
        if (fmu->setString == NULL) fmu->setString = (fmi2SetString_f)dlsym(fmu->libHandle, "{model_identifier}_fmi2SetString");
        fmu->getString = (fmi2GetString_f)dlsym(fmu->libHandle, "fmi2GetString");
        if (fmu->getString == NULL) fmu->getString = (fmi2GetString_f)dlsym(fmu->libHandle, "{model_identifier}_fmi2GetString");

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

        /* Instantiate the internal FMU with its own model identifier, GUID
         * and resource location. */
        char inner_res[MAX_RESOURCE_PATH];
        if (res_root[0] == '\\0') {{
            snprintf(inner_res, sizeof(inner_res), "resources/%s", "{fmu_id}");
        }} else {{
            snprintf(inner_res, sizeof(inner_res), "%s/resources/%s", res_root, "{fmu_id}");
        }}
        fmu->component = fmu->instantiateME(
            fmu->instance_name,
            fmi2ModelExchange,
            "{internal_guid}",
            inner_res,
            inst->callbacks,
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

        /* Enter and exit initialization mode so the FMU is ready to step */
        if (fmu->initialize) {{
            fmu->initialize(fmu->component);
        }}
        if (fmu->exitInitialize) {{
            fmu->exitInitialize(fmu->component);
        }}
    }}"""
        )
    fmu_load_code = "\n".join(fmu_load_blocks)

    # Generate variable array allocation and population code
    _c_field_name = {"real": "real", "int": "int", "bool": "bool", "str": "string"}
    _init_code = {}
    for ts, vt, caus, rs, vl in _type_role_combos:
        _init_code[f"{ts}_{rs}_init"] = _variable_mapping_init_code(
            f"inst->{_c_field_name[ts]}_{rs}s",
            [v for v in vl if v.variable_type == vt],
            "        ",
            fmu_index,
        )
    real_input_init  = _init_code["real_input_init"]
    int_input_init   = _init_code["int_input_init"]
    bool_input_init  = _init_code["bool_input_init"]
    str_input_init   = _init_code["str_input_init"]
    real_output_init = _init_code["real_output_init"]
    int_output_init  = _init_code["int_output_init"]
    bool_output_init = _init_code["bool_output_init"]
    str_output_init  = _init_code["str_output_init"]
    real_param_init  = _init_code["real_param_init"]
    int_param_init   = _init_code["int_param_init"]
    bool_param_init  = _init_code["bool_param_init"]
    str_param_init   = _init_code["str_param_init"]

    # Connections init
    connections_init_lines = []
    for idx, conn in enumerate(mapping.connections):
        connections_init_lines.append(
            f"        inst->connections_src[{idx}].vr = {conn.source_value_reference};"
        )
        connections_init_lines.append(
            f"        inst->connections_src[{idx}].fmu = &inst->internal_fmus[{fmu_index[conn.source_fmu]}];"
        )
        connections_init_lines.append(
            f"        inst->connections_tgt[{idx}].vr = {conn.target_value_reference};"
        )
        connections_init_lines.append(
            f"        inst->connections_tgt[{idx}].fmu = &inst->internal_fmus[{fmu_index[conn.target_fmu]}];"
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
                fmi2ValueReference vr = inst->real_inputs[i].internal_vr;
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
                fmi2ValueReference vr = inst->int_inputs[i].internal_vr;
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
                fmi2ValueReference vr = inst->bool_inputs[i].internal_vr;
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
                fmi2ValueReference vr = inst->string_inputs[i].internal_vr;
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
                fmi2ValueReference vr = inst->real_outputs[i].internal_vr;
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
                fmi2ValueReference vr = inst->int_outputs[i].internal_vr;
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
                fmi2ValueReference vr = inst->bool_outputs[i].internal_vr;
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
                fmi2ValueReference vr = inst->string_outputs[i].internal_vr;
                fmu->getString(fmu->component, &vr, 1, &inst->string_outputs[i].value.s);
            }
        }"""
        )
    do_step_output_code = "\n".join(do_step_output_lines)

    # Reserved wrapper parameters (master-visible solver knobs).  These are
    # wrapper-local, so the generated setters/getters route them into the
    # WrapperInstance solver fields instead of forwarding to an internal FMU.
    reserved_by_name = {v.wrapper_name: v for v in mapping.reserved_parameters}
    solver_type_vr = reserved_by_name.get(SOLVER_TYPE_PARAM)
    solver_tolerance_vr = reserved_by_name.get(SOLVER_TOLERANCE_PARAM)
    solver_step_size_vr = reserved_by_name.get(SOLVER_STEP_SIZE_PARAM)

    reserved_real_set_lines: list[str] = []
    reserved_int_set_lines: list[str] = []
    reserved_real_get_lines: list[str] = []
    reserved_int_get_lines: list[str] = []
    solver_default_lines: list[str] = []

    if mapping.reserved_parameters:
        solver_default_lines.append(
            f"    inst->solver_type = {SOLVER_TYPE_ENUM.get(spec.solver.type, 0)};"
        )
        solver_default_lines.append(
            f"    inst->solver_tolerance = {spec.solver.tolerance};"
        )

        if solver_tolerance_vr is not None:
            vr = solver_tolerance_vr.wrapper_value_reference
            reserved_real_set_lines.append(
                f"        if (vr[i] == {vr}) {{\n"
                f"            inst->solver_tolerance = value[i];\n"
                f"            continue;\n"
                f"        }}"
            )
            reserved_real_get_lines.append(
                f"        if (vr[i] == {vr}) {{\n"
                f"            value[i] = inst->solver_tolerance;\n"
                f"            continue;\n"
                f"        }}"
            )
        if solver_step_size_vr is not None:
            vr = solver_step_size_vr.wrapper_value_reference
            reserved_real_set_lines.append(
                f"        if (vr[i] == {vr}) {{\n"
                f"            inst->step_size = value[i];\n"
                f"            continue;\n"
                f"        }}"
            )
            reserved_real_get_lines.append(
                f"        if (vr[i] == {vr}) {{\n"
                f"            value[i] = inst->step_size;\n"
                f"            continue;\n"
                f"        }}"
            )
        if solver_type_vr is not None:
            vr = solver_type_vr.wrapper_value_reference
            reserved_int_set_lines.append(
                f"        if (vr[i] == {vr}) {{\n"
                f"            inst->solver_type = value[i];\n"
                f"            continue;\n"
                f"        }}"
            )
            reserved_int_get_lines.append(
                f"        if (vr[i] == {vr}) {{\n"
                f"            value[i] = inst->solver_type;\n"
                f"            continue;\n"
                f"        }}"
            )

    def _reserved_block(lines: list[str]) -> str:
        """Join generated reserved-parameter lines with a leading comment."""
        if not lines:
            return ""
        return (
            "        /* Reserved wrapper parameters (solver knobs) */\n"
            + "\n".join(lines)
            + "\n"
        )

    reserved_real_set_code = _reserved_block(reserved_real_set_lines)
    reserved_int_set_code = _reserved_block(reserved_int_set_lines)
    reserved_real_get_code = _reserved_block(reserved_real_get_lines)
    reserved_int_get_code = _reserved_block(reserved_int_get_lines)
    solver_default_code = "\n".join(solver_default_lines)

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
#include <stdarg.h>
#include <dlfcn.h>
#include <math.h>

/* ---------------------------------------------------------------------------
 * Internal FMU dynamic loading helpers
 * --------------------------------------------------------------------------- */
#define MAX_RESOURCE_PATH 1024

/* ---------------------------------------------------------------------------
 * Helper: log message through callbacks
 * --------------------------------------------------------------------------- */
static void log_message(WrapperInstance* inst, fmi2Status status, const char* category, const char* fmt, ...)
{{
    if (inst && inst->callbacks && inst->callbacks->logger) {{
        char buffer[1024];
        va_list args;
        va_start(args, fmt);
        vsnprintf(buffer, sizeof(buffer), fmt, args);
        va_end(args);
        inst->callbacks->logger(inst->callbacks->componentEnvironment,
                                inst->instance_name, status, category, buffer);
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
{solver_default_code}
    inst->algebraic_loop_max_iterations = {spec.solver.algebraic_loop.max_iterations};
    inst->algebraic_loop_tolerance = {spec.solver.algebraic_loop.tolerance};
    inst->num_algebraic_loops = {len(mapping.algebraic_loops)};

    /* Count internal FMU variables */
    inst->num_internal_fmus = {num_fmus};
    inst->internal_fmus = (InternalFMU*)calloc({num_fmus}, sizeof(InternalFMU));
    if (inst->internal_fmus == NULL) {{ free(inst); return NULL; }}

    /* Load all internal FMUs */
{fmu_load_code}

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
{reserved_real_get_code}
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
{reserved_real_set_code}
        /* Check wrapper inputs */
        int found = 0;
        for (int j = 0; j < inst->num_real_inputs; j++) {{
            if (inst->real_inputs[j].vr == vr[i]) {{
                inst->real_inputs[j].value.r = value[i];
                found = 1;

                /* Propagate to internal FMU if connected */
                if (inst->real_inputs[j].fmu) {{
                    InternalFMU* fmu = (InternalFMU*)inst->real_inputs[j].fmu;
                    fmi2ValueReference tgt_vr = inst->real_inputs[j].internal_vr;
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
                        fmi2ValueReference tgt_vr = inst->real_params[j].internal_vr;
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
{reserved_int_get_code}
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
{reserved_int_set_code}
        int found = 0;
        for (int j = 0; j < inst->num_int_inputs; j++) {{
            if (inst->int_inputs[j].vr == vr[i]) {{
                inst->int_inputs[j].value.i = value[i];
                found = 1;
                if (inst->int_inputs[j].fmu) {{
                    InternalFMU* fmu = (InternalFMU*)inst->int_inputs[j].fmu;
                    fmi2ValueReference tgt_vr = inst->int_inputs[j].internal_vr;
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
                        fmi2ValueReference tgt_vr = inst->int_params[j].internal_vr;
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
                    fmi2ValueReference tgt_vr = inst->bool_inputs[j].internal_vr;
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
                        fmi2ValueReference tgt_vr = inst->bool_params[j].internal_vr;
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
                    fmi2ValueReference tgt_vr = inst->string_inputs[j].internal_vr;
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
                        fmi2ValueReference tgt_vr = inst->string_params[j].internal_vr;
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
        double h;
        if (inst->solver_type == 1) {{
            /* Variable-step mode: evolve toward the communication point */
            h = t_end - t;
        }} else {{
            /* Fixed-step mode: slice the communication step by step_size */
            h = (t + inst->step_size <= t_end) ? inst->step_size : (t_end - t);
        }}
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
        double t_out = t;
        int result = solver_step(inst, t, h, &t_out);
        if (result != 0) {{
            log_message(inst, fmi2Error, "solver", "Solver step failed at t=%g", t);
            inst->state = WrapperState_Error;
            return fmi2Error;
        }}
        if (t_out <= t) {{
            log_message(inst, fmi2Error, "solver", "Solver did not advance at t=%g", t);
            inst->state = WrapperState_Error;
            return fmi2Error;
        }}
        t = t_out;
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