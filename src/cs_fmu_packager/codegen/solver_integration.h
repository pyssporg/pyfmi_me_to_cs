/* solver_integration.h - Header for SUNDIALS ARKODE integrator. */

#ifndef SOLVER_INTEGRATION_H
#define SOLVER_INTEGRATION_H

#include "fmi2_interface.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Initialize the SUNDIALS solver */
int solver_init(WrapperInstance* wrapper);

/* Perform one integration step */
int solver_step(WrapperInstance* wrapper, double t0, double h);

/* Free solver resources */
void solver_free(WrapperInstance* wrapper);

#ifdef __cplusplus
}
#endif

#endif /* SOLVER_INTEGRATION_H */