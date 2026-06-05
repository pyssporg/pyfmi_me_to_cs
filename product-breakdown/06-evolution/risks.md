# Risks

| ID | Risk | Likelihood | Impact | Mitigation |
| --- | --- | --- | --- | --- |
| RISK-001 | Fixed-point iteration does not converge for strongly nonlinear algebraic loops | Medium | High — blocks UC-001 (SCC packaging) for problematic systems | Make max_iterations and tolerance configurable; document convergence limitations; consider delayed-feedback fallback in future |
| RISK-002 | Internal FMU shared libraries fail to load via dlopen at runtime | Medium | High — FMU unusable | Validate internal FMU binary availability during packaging; document dlopen requirements |
| RISK-003 | SUNDIALS API changes break the solver integration | Low | Medium — requires codegen update | Pin SUNDIALS version via vcpkg baseline; capture solver version in build report |
| RISK-004 | FMI 3.0 adoption makes the FMI 2.0-only design obsolete | Low (short-term) | High (long-term) | CR-003 states design should not prevent later FMI 3.0 support; architecture separates FMI interface from solver core |
| RISK-005 | Single-platform (Linux x86_64) limits adoption | Medium | Medium — excludes Windows/macOS users | AD-006 explicitly acknowledges this as a v1 tradeoff; binaries/ directory structure supports future platform additions |
| RISK-006 | TOML spec format is not a standard simulation interchange format | Low | Low — TOML is widely supported | SPR-007 requires version-control friendliness; TOML meets this; SSP support could be added as an alternative input format later |