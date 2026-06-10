# Traceability Map

## Trace Chain 1: Single FMU Packaging

```
INT-001 Provide reusable ME-to-CS packaging mechanism
  -> CAP-001 Package Model Exchange FMUs into Co-Simulation FMU
    -> UC-001 Package a Strongly Connected Component
      -> FR-001 Package one or more ME FMUs into one CS FMU
        -> AD-001 C Wrapper Architecture (generate C source → native .so)
          -> 02-architecture/component-view.md (6-phase pipeline)
            -> 03-implementation/modules/codegen-fmi-interface.md (fmi2_interface.c generation)
              -> 04-verification/test-cases/test_end_to_end.md (test_assembled_fmu_structure)
```

## Trace Chain 2: Solver Integration

```
INT-002 Enable configurable local solver placement
  -> CAP-002 Support configurable local solver
    -> UC-002 Wrap a Tightly Coupled Physical Subsystem
      -> FR-010 Support at least one deterministic local solver
        -> SR-001 Fixed-step explicit solver for ME FMUs
          -> AD-002 SUNDIALS Solver (ARKODE fixed-step)
            -> 02-architecture/integration-view.md (SUNDIALS ARKODE integration)
              -> 03-implementation/modules/codegen-solver.md (solver_integration.c generation)
                -> 04-verification/test-cases/test_codegen.md (TestCmakeCodegen, TestModelDescriptionCodegen)
```

## Trace Chain 3: Algebraic Loop Handling

```
INT-003 Support coupled subsystems with feedback
  -> CAP-003 Handle algebraic loops in internal connections
    -> UC-001 Package a Strongly Connected Component
      -> FR-005 (algebraic loop configuration)
        -> SR-005 Define behavior for algebraic/direct-feedthrough loops
          -> AD-003 Fixed-Point Iteration for Algebraic Loops
            -> 02-architecture/component-view.md (mapper phase)
              -> 03-implementation/modules/mapper.md (pyssp_standard connection_graph delegate)
              -> 03-implementation/modules/codegen-fixed-point.md (fixed_point_iteration.c)
                -> 04-verification/test-cases/test_mapper.md (test_algebraic_loop_detection_internal)
```

## Trace Chain 4: Declarative Specification

```
INT-004 Enable reproducible, automatable packaging
  -> CAP-004 Accept declarative package specification
    -> UC-006 Generate Co-Simulation FMUs from a Declarative Spec
      -> FR-002 Accept declarative package spec describing FMUs, connections, solver
        -> SPR-001 through SPR-007 (specification format requirements)
          -> AD-005 TOML Spec Format
            -> 02-architecture/data-view.md (PackageSpec → MappingTable)
              -> 03-implementation/modules/spec.md (TOML parsing and validation)
              -> 03-implementation/modules/models.md (PackageSpec dataclasses)
                -> 04-verification/test-cases/test_spec_validation.md (13 tests)
```

## Trace Chain 5: Deterministic Artifacts

```
INT-005 Support reproducible experiments
  -> CAP-005 Produce deterministic, reproducible generated artifacts
    -> UC-003 Compare Solver Placement Alternatives
      -> FR-018 Support deterministic artifact naming
        -> NFR-001 Generated artifacts reproducible from same inputs
          -> AD-004 Embedded FMU Resources (self-contained FMU)
            -> 02-architecture/deployment-view.md (FMI standard directory convention)
              -> 03-implementation/modules/packager.md (fixed ZIP timestamps, sorted entries)
                -> 04-verification/test-cases/test_end_to_end.md (test_deterministic_content)
```

## Trace Chain 6: Platform Constraint

```
CON-001 First version targets Linux x86_64 only
  -> AD-006 Linux x86_64 Only (v1)
    -> 02-architecture/deployment-view.md (single platform)
      -> 03-implementation/modules/builder.md (Linux CMake config)
      -> 03-implementation/environments.md (Linux x86_64, GCC, CMake)
        -> CMakePresets.json (Linux build preset)
```