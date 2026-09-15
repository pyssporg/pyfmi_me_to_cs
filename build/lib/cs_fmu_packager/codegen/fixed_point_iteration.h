/* fixed_point_iteration.h - Header for algebraic loop solver. */

#ifndef FIXED_POINT_ITERATION_H
#define FIXED_POINT_ITERATION_H

#include "fmi2_interface.h"

#ifdef __cplusplus
extern "C" {
#endif

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

/* Resolve all algebraic loops in the wrapper */
int fixed_point_resolve_all(WrapperInstance* wrapper, double time);

#ifdef __cplusplus
}
#endif

#endif /* FIXED_POINT_ITERATION_H */