# Users

The following user types are identified for the cs-fmu-packager:

| User Type | Description |
| --- | --- |
| Simulation Architect | Wants to move a tightly coupled subsystem behind one Co-Simulation boundary. Makes architectural decisions about decomposition and solver placement. |
| Experiment Developer | Needs reproducible variants of the same logical system with different solver boundaries. Interested in automation and deterministic artifact generation. |
| FMI Tool Developer | Needs a reference wrapper pattern for ME-to-CS packaging. May inspect the generated C code as a reference implementation. |
| Researcher | Compares decomposition, scheduling, and solver-placement effects. Benefits from traceable, reproducible packaging boundaries. |

## Source

Derived from `cs-fmu-packager-project/README.md` (Intended Users section).