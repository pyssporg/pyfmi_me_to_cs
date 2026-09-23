/* fixed_point_iteration.h - Header for internal coupling / algebraic loop solver. */

#ifndef FIXED_POINT_ITERATION_H
#define FIXED_POINT_ITERATION_H

#include "fmi2_interface.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Propagate all internal connections once (source -> target) at the current
 * internal-FMU state.  Resolves the acyclic part of the connection graph. */
void wrapper_propagate_connections(WrapperInstance* wrapper);

/* Solve a single algebraic loop using fixed-point iteration */
int fixed_point_solve_loop(
    InternalFMU* fmus,
    int num_fmus,
    VariableMapping* connections_src,
    VariableMapping* connections_tgt,
    int num_connections,
    int max_iterations,
    double tolerance,
    double time);

/* Resolve the internal coupling at the current state and time by
 * fixed-point iteration until convergence or the configured iteration
 * limit.  Returns 0 on success, -1 on allocation failure. */
int wrapper_resolve_coupling(WrapperInstance* wrapper, double time);

#ifdef __cplusplus
}
#endif

#endif /* FIXED_POINT_ITERATION_H */
