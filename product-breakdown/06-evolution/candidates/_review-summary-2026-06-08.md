# Candidate Review Summary — 2026-06-08

## Scope

This review captures 12 improvement candidates (IMP-015 through IMP-026) across three themes:

1. **Dead code and dependency cleanup** (IMP-015 through IMP-019) — removal of unused dependencies, imports, data fields, and dead functions
2. **Code consolidation and DRY refactoring** (IMP-020 through IMP-023, IMP-026) — reducing repetition in codegen call sites, XML parsing, and test setup
3. **Strategic evaluations** (IMP-024, IMP-025) — deferred evaluations of larger architectural changes

## Priority-Ordered Candidate Table

| Priority | IMP  | Title | Primary Files | Gain | Risk | Theme |
|---|---|---|---|---|---|---|
| **P1** | IMP-015 | Remove dead `Jinja2` dependency and orphaned templates | `pyproject.toml`, `c_templates/*.jinja` | High | Zero | Dependency cleanup |
| **P2** | IMP-016 | Remove unused imports across source files | `cli.py`, `builder.py`, `packager.py`, `models.py` | Moderate | Zero | Code cleanup |
| **P3** | IMP-017 | Remove dead `_vr_for_index()` in `model_description.py` | `model_description.py` | Low | Zero | Code cleanup |
| **P4** | IMP-018 | Remove unused `_VARIABLE_REF_RE = None` in `spec.py` | `spec.py` | Low | Zero | Code cleanup |
| **P5** | IMP-019 | Remove unused `FmuMetadata.variables_by_ref` field | `models.py`, `fmu_reader.py` | Low | Zero | Data model cleanup |
| **P6** | IMP-020 | Consolidate 12× `_variable_mapping_init_code()` calls | `codegen/fmi_interface.py` | Moderate | Low | Code consolidation |
| **P7** | IMP-021 | Consolidate 12× `_count_type()` calls | `codegen/fmi_interface.py` | Low | Low | Code consolidation |
| **P8** | IMP-022 | Eliminate redundant `_parse_variable_ref()` calls | `spec.py` | Low | Low | Optimization |
| **P9** | IMP-023 | Unify duplicate XML fallback patterns | `fmu_reader.py` | Low | Low | Code consolidation |
| **P10** | IMP-026 | Merge test fixture/helper patterns into `conftest.py` | `tests/` (cross-file) | Low-Moderate | Low | Test infrastructure |
| **P11** | IMP-024 | Evaluate migrating C codegen to Jinja2 templates | Codegen modules, `c_templates/` | Mixed | Moderate-High | Architecture evaluation |
| **P12** | IMP-025 | Evaluate fmpy for test infrastructure simplification | `tests/` | Low | Moderate | Test evaluation |

## Priority Rationale

**P1–P5 (zero-risk removals):** Sorted by gain. IMP-015 (dependency removal) is highest gain. IMP-016 (unused imports) is moderate gain. IMP-017, IMP-018, IMP-019 are low-gain cleanups.

**P6–P10 (low-risk refactoring):** Sorted by gain. IMP-020 (moderate gain, codegen call-site consolidation) is the most impactful. IMP-026 (test helper consolidation) adds cross-file value. IMP-021, IMP-022, IMP-023 are smaller targeted improvements.

**P11–P12 (deferred evaluations):** Both are strategic evaluations rather than implementation candidates. IMP-024 (Jinja2 codegen) is captured for future reference but not recommended for near-term execution. IMP-025 (fmpy leverage) is captured as a low-priority exploration.

## Interaction Notes

- **IMP-015 ↔ IMP-024:** IMP-015 proposes removing the `Jinja2` dependency; IMP-024 proposes re-activating it for C codegen. If IMP-015 is done first, IMP-024 must reverse the removal. They should be handled in sequence with a decision on which direction to take.
- **IMP-020 ↔ IMP-021:** Both touch the same file (`fmi_interface.py`) and the same structural pattern (12× repeated calls). They should be implemented in the same work order to avoid merge conflicts.
- **IMP-022 ↔ IMP-018:** Both touch `spec.py` but affect different concerns (variable ref parsing vs. regex placeholder).
- **IMP-026 ↔ IMP-014, IMP-025:** Shared test helpers should be compatible with Modelica-backed fixture generation (IMP-014) and any fmpy adoption (IMP-025).

## Cross-References to Existing Candidates

| Existing Candidate | Related New Candidate | Relationship |
|---|---|---|
| IMP-001 (README rewrite) | IMP-026 (test helpers) | Both improve developer onboarding but different domains |
| IMP-007 (vcpkg error message) | IMP-015 (dependency removal) | Both reduce user confusion |
| IMP-014 (Modelica fixtures) | IMP-025 (fmpy evaluation), IMP-026 (test helpers) | Test infrastructure theme |

## Decision Log

| Decision | Rationale |
|---|---|
| IMP-024 deferred (not recommended now) | Large refactoring (~1600 lines), high risk, unclear benefit over f-strings for current codegen volume. Capture as strategic reference. |
| IMP-025 deferred (not recommended now) | Fmpy already used in behavioral verification; replacing the project's own `fmu_reader.py` tests with fmpy would change what is being tested. Capture as exploration for future. |

## Lessons Referenced

- PAT-001 (tests as specifications) — applied to IMP-026 to limit test helper abstraction
- DRY principle — applied to IMP-020, IMP-021, IMP-023, IMP-026
- Zero-risk removal first — applied to priority ordering (P1–P5 before P6–P12)

## File Inventory

| File | Candidates Covered |
|---|---|
| `product-breakdown/06-evolution/candidates/IMP-015.md` | C1 — Remove Jinja2 dependency |
| `product-breakdown/06-evolution/candidates/IMP-016.md` | C2 — Remove unused imports |
| `product-breakdown/06-evolution/candidates/IMP-017.md` | C3 — Remove `_vr_for_index()` |
| `product-breakdown/06-evolution/candidates/IMP-018.md` | C4 — Remove `_VARIABLE_REF_RE` |
| `product-breakdown/06-evolution/candidates/IMP-019.md` | C5 — Remove `variables_by_ref` |
| `product-breakdown/06-evolution/candidates/IMP-020.md` | C6 — Consolidate `_variable_mapping_init_code()` |
| `product-breakdown/06-evolution/candidates/IMP-021.md` | C7 — Consolidate `_count_type()` |
| `product-breakdown/06-evolution/candidates/IMP-022.md` | C8 — Eliminate redundant `_parse_variable_ref()` |
| `product-breakdown/06-evolution/candidates/IMP-023.md` | C9 — Unify XML fallback patterns |
| `product-breakdown/06-evolution/candidates/IMP-024.md` | C10 — Evaluate Jinja2 codegen |
| `product-breakdown/06-evolution/candidates/IMP-025.md` | C11 — Evaluate fmpy in tests |
| `product-breakdown/06-evolution/candidates/IMP-026.md` | C12 — Merge test fixture helpers |
| `product-breakdown/06-evolution/candidates/_review-summary-2026-06-08.md` | This file — aggregate summary |

## Next Steps

1. Review and approve priority ordering
2. Select candidates for work order creation — start with P1–P5 (zero-risk, independent, high-confidence)
3. Coordinate P6+P7 (IMP-020+IMP-021) as a single work order
4. File IMP-024 and IMP-025 under "strategic backlog" for future reference