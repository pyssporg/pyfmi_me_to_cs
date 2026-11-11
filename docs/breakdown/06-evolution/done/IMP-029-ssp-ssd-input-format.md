# IMP-029: Adopt a complete SSP package (`.ssp` with embedded FMUs) as the sole package specification input — remove TOML

Use this template for one backlog-ready improvement candidate.

An improvement candidate is not implementation approval. It needs a scoped task contract before code or documentation changes begin.

## Lifecycle Stage

Done

## Status

Completed (2026-09-15)

## Layer

Evolution (primary). Downstream layers: 01-product (UC-006 declarative spec), 02-architecture (AD-005 supersession), 03-implementation (ssp_spec.py, cli.py), 04-verification (test_ssp_spec.py).

## Theme

Input format standardization, standard simulation interchange, pyssp_standard SSP1 leverage, boundary variable exposure, duplicate-format elimination

## Evidence

### Scope Definition

This candidate **replaces** the project-specific TOML package spec with a **complete SSP package** (`.ssp`) as the **only** input format of `cs-fmu-packager`. A `.ssp` is a self-contained archive that always embeds its internal FMUs alongside the `SystemStructure.ssd` description document. The internal contract (`PackageSpec` → `MappingTable` → codegen/packager) is unchanged; only the front-end changes, and the TOML front-end is **removed**.

**Streamlined-workflow assumption (explicit):** the input is *always* a complete `.ssp` container. There is no standalone `.ssd` mode, no TOML, and no external file-path references — all FMUs live inside the archive and are referenced through relative source URIs. The packager extracts what it needs from the archive during assembly, so the workflow is one self-contained artifact in, one CS FMU out.

**Design assumption (explicit):** *all* internal FMU inputs, outputs, and parameters are **wired to the edge** — each becomes a top-level system connector on the SSD — so that every internal value can be **get/set/viewed** at the packaged CS FMU boundary. This mirrors the current auto-discovery semantics (`[[variables]]` optional; IMP-013) and makes the boundary explicit in the SSD.

### Existing Project Signals

- `src/cs_fmu_packager/spec.py` — 345 lines, TOML-only parsing into `PackageSpec` (FmuRef, Connection, WrapperVariable, SolverConfig, WrapperConfig). This is the entire (and only) input surface, and it is non-standard.
- `pyproject.toml` — declares `toml>=0.10` solely for `spec.py`; removable with it.
- `src/cs_fmu_packager/cli.py` — `SPEC` positional argument; format is implicitly TOML; needs to route to the SSP front-end.
- `tests/test_spec_validation.py` — 13 spec-validation tests that encode the TOML dialect; must be replaced, not migrated.
- `product-breakdown/02-architecture/decisions/AD-005-toml-spec-format.md` — chose TOML for v1 over SSP "for future import/export", with review trigger: *"If standard simulation interchange formats (SSP, FMI SSP) gain widespread adoption and users request direct import/export."*
- `product-breakdown/06-evolution/risks.md` (RISK-006) — *"TOML spec format is not a standard simulation interchange format"*; mitigation noted *"SSP support could be added as an alternative input format later."* Superseded: SSP is now the *only* input.
- `product-breakdown/01-product/use-cases/UC-006.md` — the primary actor is an **upstream generator** that "produces a package specification from a graph, SysML model, **SSP model**, or other architecture description." SSP is already named as a source.
- `README.md` Quickstart, `03-implementation/modules/spec.md`, `models.md`, Trace Chain 4, and the 4 end-to-end tests all instantiate TOML specs; all must switch to `.ssp`.

### Library Leverage (no new dependency)

The installed `pyssp_standard` (hard dependency since IMP-025) already ships a complete SSP 1.0 stack:

| Component | Module | API |
|---|---|---|
| SSD model | `pyssp_standard/standard/ssp1/model/ssd_model.py` | `Ssd1SystemStructureDescription`, `Ssd1System`, `Ssd1Component`, `Ssd1Connector`, `Ssd1Connection`, `Ssd1DefaultExperiment`, `Ssd1ParameterBinding`, `Ssp1ParameterSet` |
| SSD XML codec | `pyssp_standard/standard/ssp1/codec/ssd_codec.py` | `Ssp1SsdCodec().parse(xml_text) -> Ssd1SystemStructureDescription`, `.serialize(doc) -> str` |
| Operations | `standard/ssp1/operations/` | `ssd_flatten`, `ssd_parameters`, `ssd_parameter_bindings`, `ssd_fmu_iteration`, `model_description_to_ssd` |
| Validation | `standard/ssp1/validation/ssd_validation.py` | SSD schema validation |
| Schemas | `schema/SSP1/*.xsd` | `SystemStructureDescription11.xsd`, `SystemStructureParameterValues.xsd`, etc. |

**Verified in this checkout:** `Ssp1SsdCodec().serialize`/`.parse` round-trips a minimal document (1 component, 1 connector, 1 connection) in `.venv` Python 3.10.

### Concept Mapping (legacy TOML concepts → SSP 1.0 SSD)

| TOML concept (spec.py) | `PackageSpec` field | SSP 1.0 SSD representation |
|---|---|---|
| `[metadata] identifier` | `metadata` | `SystemStructure` `name`/`version` attributes (+ optional `metadata/` in the archive) |
| `[fmus] <id> = { path, kind, fmi_version }` | `fmus: Dict[str, FmuRef]` | `<Elements><Component name="<id>" source="<relative URI in archive>" type="application/x-fmu-sharedlibrary"/></Elements>` — `source` always resolves **inside the `.ssp` archive** |
| `[[connections]] source/target` (`fmu.var`) | `Connection` | `<Connections><Connection startElement="<src_fmu>" startConnector="<src_var>" endElement="<tgt_fmu>" endConnector="<tgt_var>"/></Connections>` |
| `[[variables]] name/type/causality/source/target/start` | `WrapperVariable` | System-level `<Connectors><Connector element="<fmu>/<var>" name="<boundary name>" kind="<input\|output\|parameter\|calculatedParameter\|inout>"/></Connectors>`; `start` via `ParameterBindings` / `ParameterSet` |
| `[solver] type/step_size/communication_step/algebraic_loop` | `SolverConfig` | **Not representable in SSP 1.0** (`Ssd1DefaultExperiment` exposes only `start_time`/`stop_time`) → vendor annotation (see Proposed Improvement) |
| `[wrapper] communication_step` | `WrapperConfig` | **Not representable in SSP 1.0** → vendor annotation |

## Current Pain Or Risk

- **The only input format is project-specific.** The declared primary actor (UC-006) is an **automated upstream generator**, yet the tool ingests a custom TOML dialect. SSP-based toolchains (graph/plant models, SysML, SSP masters such as ssp4sim) cannot drive the packager directly; users must re-serialize their architecture into `fmu.var` strings and TOML tables.
- **RISK-006 is realized:** TOML is not a standard simulation interchange format, and keeping it means maintaining declaration, validation, and documentation with no standard-compatibility benefit.
- **Duplicate format machinery:** `spec.py` (345 lines), its 13 tests, and the `toml` runtime dependency exist solely for a single non-standard dialect that pyssp_standard can already express with its bundled SSP1 codec.
- **AD-005 review trigger is met** — the review predicate ("SSP gains widespread adoption and users request direct import/export") has been reached in the surrounding ecosystem; this candidate is the SME action the architecture explicitly deferred to.
- **Boundary exposure is implicit today.** Without an explicit rule, whether an internal value is settable/readable at the edge depends on what `[[variables]]` the author happens to list. The edge-wiring default below makes the boundary contract deterministic and self-documenting in the SSD.

## Proposed Improvement

1. **New front-end module `src/cs_fmu_packager/ssp_spec.py`** — `parse_spec(path) -> PackageSpec` accepting a **complete `.ssp` archive**:
   - `SystemStructure.ssd` is read from the archive root, and every embedded resource (the internal FMUs referenced by `<Component source="...">`) is resolved **inside the archive** as relative URIs.
   - During packaging, the packager extracts the needed FMUs from the archive into the build workspace and embeds them in the output CS FMU (per AD-004).
   - Implementation uses `Ssp1SsdCodec().parse()` → `Ssd1SystemStructureDescription`, then a normalization layer to `PackageSpec`, leaving `mapper`, `codegen`, `packager`, and the downstream test suite untouched.

2. **Normalization layer (SSD → PackageSpec):**
   - `<Component>` → `FmuRef` (resolve `source` URI **within the archive**; verify `type` is `application/x-fmu-sharedlibrary`).
   - `<Connection>` → `Connection` (`startElement`/`startConnector`/`endElement`/`endConnector`).
   - System `<Connector>` → `WrapperVariable` (`kind` maps to `causality`; `type_name`/`type_attributes` map to `type`/`unit`).
   - `<ParameterBinding>` with started values → `WrapperVariable.start`.

3. **Edge-wiring default (the assumption).** Every internal FMU variable — inputs, outputs, parameters, calculated parameters — is emitted as a top-level system `<Connector>` (kind per FMI causality/variability, e.g. `input`/`output`/`parameter`/`calculatedParameter`), so all internal values are get/set/viewable at the packaged CS FMU boundary. Variables that are also connection endpoints keep their boundary connector (exactly like today's auto-discovery). `start` values carried by `ParameterBindings` become wrapper variable start values.

4. **Solver/wrapper configuration representation.** SSP 1.0 has no step-size/communication-step semantics. Propose:
   - Represent `fixed_step`/`step_size`/`communication_step`/`algebraic_loop` in a **vendor `<Annotations>`** block on the SSD (`Ssp1Annotation` is already supported by the model/codec), namespaced to `cs-fmu-packager`. This is now the **canonical carrier** of solver policy — no companion format exists.
   - **Fall back to current defaults** when the annotation is absent.
   - Allow **CLI overrides** (`--step-size`, `--communication-step`) as a non-XML escape hatch.
   - No standard SSP elements are invented; the annotation is optional and ignorable by other tools.

5. **Remove the TOML front-end** (in scope):
   - Delete `src/cs_fmu_packager/spec.py` and `tests/test_spec_validation.py`.
   - Drop `toml>=0.10` from `pyproject.toml`.
   - Rewrite `README.md` Quickstart, `03-implementation/modules/spec.md`, `models.md`, Trace Chain 4, `04-verification/test-cases/test_spec_validation.md`, and any fixtures/end-to-end tests that instantiate TOML specs — all now `.ssp`-based.
   - Supersede AD-005 (TOML Spec Format) with the new SSP decision (see Decision-Log Entry Suggestion).
   - Existing TOML spec files are not auto-migrated; the Concept Mapping table above serves as the migration guide, and the migration burden is documented (see Notes).

## Expected Benefit

- **One standard, one front-end:** a single self-contained `.ssp` artifact carries structure *and* FMUs — no path/state management, no dialect to maintain, no `toml` dependency, no duplicate test surface (~345-line parser + 13 tests removed).
- **Standard interchange:** SSP-based upstream generators become first-class (and only) inputs, closing the UC-006 gap; output CS FMUs can be re-embedded into SSP assemblies by external masters.
- **Zero new dependencies:** reuses the installed `pyssp_standard` SSP1 stack (model, codec, operations, validation, XSDs); strictly *reduces* the dependency set by dropping `toml`.
- **Deterministic, explicit boundary:** the edge-wiring default guarantees every internal I/O/parameter is controllable/observable at the boundary by construction, documented in the SSD itself.
- **Decision/risk closure:** RISK-006 resolved (formats standardized); AD-005 superseded by an accepted SSP decision; `spec.md`/`models.md`/README describe one canonical format.

## Risk And Blast Radius

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Solver/wrapper config has no SSP 1.0 element | High | Medium | Vendor `<Annotations>` (canonical) + defaults + CLI overrides; never invent standard elements |
| Breaking change for existing TOML spec users | High | Medium | Documented migration via the Concept Mapping table; v0.1.x → 0.2.0 (semver) release note; upstream generator path receives the `.ssp` producer contract |
| Fork/canonical SSD variance: installed codec root/namespace (`ssd:SystemStructureDescription` @ `http://ssp-standard.org/SSP1/SystemStructureDescription`) vs ecosystem SSP peers — root/namespace must be confirmed per target toolchain | Medium | Medium | Contract step: pin target SSP version; add an XSD/namespace conformance test |
| Connector kind vs FMI causality edge cases (`calculatedParameter`, `inout`, mismatches) | Medium | Medium | Map through existing `_resolve_fmu_variable`/mapper semantics; validation errors aggregated as today |
| Variable both internally connected and edge-exposed (dedup/aliasing) | Medium | Low | Reuse auto-discovery rules; assign boundary names deterministically (NFR-001) |
| Blast radius (TOML removal) | — | Medium (input + docs + tests) | `PackageSpec` contract preserved; mapper/codegen/packager untouched; all TOML-only surface is deleted, not patched |

## Suggested Priority

Medium (same tier as IMP-025/IMP-027; unblocks UC-006 SSP actor)

## Selected Date

N/A

## Completed Date

N/A

## Implementation Reference

- **Dependency:** `pyssp-standard>=0.8` (already a hard dependency; SSP1 stack confirmed present in the installed fork `jkCXf9X4/pyssp_standard@architecture_review`). `toml>=0.10` removed.
- **Related artifacts:** AD-005 (`02-architecture/decisions/AD-005-toml-spec-format.md` — superseded), RISK-006 (`06-evolution/risks.md`), UC-006 (`01-product/use-cases/UC-006.md`), Trace Chain 4 (`traceability-map.md`), IMP-013/IMP-025/IMP-027.
- **Key files changed (when contracted):** `src/cs_fmu_packager/ssp_spec.py` (new), `src/cs_fmu_packager/spec.py` (deleted), `src/cs_fmu_packager/cli.py`, `pyproject.toml` (drop `toml`), `README.md`, `product-breakdown/03-implementation/modules/spec.md`, `tests/test_ssp_spec.py` (new), `tests/test_spec_validation.py` (deleted).

## Task Contract Seed

- [ ] Pin the target SSP version/namespace: compare the installed `Ssp1SsdCodec` output against `ssp4sim`/OMC expectations; record the XML root (`SystemStructure` vs `SystemStructureDescription`) and namespace decision
- [ ] Prototype `parse_spec()` for a small `.ssp` archive (2 chained FMUs, 2 boundary connectors) and assert the resulting `PackageSpec` matches the concepts of the current spec
- [ ] Cover complete-`.ssp` archive reading: `SystemStructure.ssd` from archive root, relative `<Component source>` URIs resolved inside the archive, extraction of FMUs into the build workspace feeding `assemble_fmu` (AD-004)
- [ ] Implement edge-wiring default: emit a system `<Connector>` for every internal input/output/parameter/calculatedParameter; verify get/set/view at the packaged CS FMU boundary (reuse `test_end_to_end` boundary assertions)
- [ ] Define the vendor `<Annotations>` schema for solver/wrapper config + fallback/override precedence (canonical carrier)
- [ ] Add `tests/test_ssp_spec.py` (parse archive, normalize, edge-wiring, error aggregation)
- [ ] Delete `spec.py`, `test_spec_validation.py`; drop `toml>=0.10` from `pyproject.toml`
- [ ] Rewrite `README.md` Quickstart, `spec.md`, `models.md`, `test-cases/test_spec_validation.md`, and any TOML fixtures/end-to-end tests to `.ssp`
- [ ] Supersede AD-005 with a new SSP decision; resolve RISK-006 in `risks.md`
- [ ] Re-evaluate SPR-001 through SPR-007 against SSD semantics (version-control friendliness, explicit FMU refs/connections hold; solver-policy requirement shifts to the vendor annotation) and record the outcome
- [ ] Release note for 0.2.0: TOML input removed; migration guide references the Concept Mapping table

## Out Of Scope

- Changing the downstream pipeline contract (`PackageSpec`, `mapper.py`, codegen, packager) or generated CS FMU structure
- Emitting `.ssp` output — the packager still produces a plain CS FMU; SSP output is a separate candidate
- Standalone `.ssd`-file input or external (non-archive) FMU path resolution — the input is always a complete `.ssp` container
- Any TOML support, including an automated `toml -> ssp` converter, a `--spec-format` selector, or keeping `spec.py` dormant
- FMI 3.0 / SSP 2.0 support (present in the library but deferred)

## Traceability

- **Intent:** Enable standard SSP interchange and a deterministic, explicit boundary per UC-006; resolve RISK-006 by removing the non-standard format entirely.
- **Product:** Input capability (CAP-004/FR-002 declarative spec) is now expressed solely as an SSP SSD; edge-wiring default as a product-level contract.
- **Architecture:** AD-005 superseded; single front-end (`ssp_spec.py`) with a single normalization target; vendor annotation convention for solver policy.
- **Implementation:** `ssp_spec.py` (SSP1 codec + normalization), `cli.py` routing, `spec.py`/`test_spec_validation.py`/`toml` dependency removed.
- **Verification:** `test_ssp_spec.py` replaces `test_spec_validation.py`; existing end-to-end boundary assertions reused for edge-wiring.

## Notes

### Design Assumption (recorded)

All internal FMU inputs, outputs, and parameters are wired to the edge (system-level connectors) to enable get/set/view of internal values at the packaged CS FMU boundary. This is not a new behavior — it matches current auto-discovery when `[[variables]]` is omitted — but it becomes an **explicit, default-on contract** in the SSD representation.

### Streamlined-Workflow Assumption (recorded)

The input is **always a complete `.ssp` container** with internal FMUs embedded — never a bare `.ssd` referencing external filesystem paths, and never TOML. This removes path/state management between spec and resources and keeps the packager's contract to one self-contained artifact.

### Migration Burden (recorded)

Removing TOML is a breaking change for existing spec files. No automated converter is provided (any TOML machinery is out of scope by design). The **Concept Mapping** table above is the reference document; a one-off scripted migration may be run by users locally, but the product ships SSP-only. This is acceptable because the declared primary actor is an upstream generator (UC-006), not an author of hand-written TOML.

### Duplicate Check

- `IMP-025` (fmpy/pyssp_standard ZIP/XML leverage) — orthogonal; SSP parsing is a *new* library capability use, not a parsing-site replacement.
- `IMP-027` (pyssp_standard graph/FMI-dataclass/FMU-creation overlap) — orthogonal; this candidate uses `standard/ssp1/*`, not the modules audited there.
- `IMP-024` (Jinja2 codegen), `IMP-023` (XML fallback in fmu_reader), `IMP-002` (example TOML spec — removed with the format) — not overlapping.
- No existing candidate or done item covers SSP input. AD-005 and RISK-006 are the only prior mentions, both deferring exactly this.
- Potential future interplay: IMP-028 (multi-FMU composite codegen blocker) is the runtime prerequisite for any real multi-FMU `.ssp` being executed; this candidate is independent but its acceptance tests benefit from IMP-028 being fixed.

### Relationship to `undeveloped sugestions.md`

The intent bullet "create comprehensive usage… documentation under docs/" and the SSP connection in UC-006 both benefit: an SSD input gives a canonical, standard example spec format to document.

### Decision-Log Entry Suggestion

Recorded as:
```
| AD-IMP-029-SSP | Adopt complete `.ssp` as sole package specification input (SSP 1.0 SSD + embedded FMUs) | Architecture | Accepted | `06-evolution/done/IMP-029-ssp-ssd-input-format.md` | `src/cs_fmu_packager/ssp_spec.py`, `src/cs_fmu_packager/spec.py` (deleted), `src/cs_fmu_packager/cli.py`, `pyproject.toml`, `tests/test_ssp_spec.py` |
| AD-005 (REVOKED) | TOML Spec Format | Architecture | Superseded by AD-IMP-029-SSP | `02-architecture/decisions/AD-005-toml-spec-format.md` | `06-evolution/done/IMP-029-ssp-ssd-input-format.md` |
```

## Completion Notes

Implemented 2026-09-15:

- **New front-end** `src/cs_fmu_packager/ssp_spec.py` — `parse_spec(path, workspace_dir=None)` reads a complete `.ssp` archive (namespace-tolerant `SystemStructure.ssd` parsing via `pyssp_standard`'s `Ssp1SsdCodec`), extracts embedded FMUs into a caller-owned workspace (`weakref` cleanup when unmanaged), and normalizes to `PackageSpec`. Level-1 validation re-implements the removed TOML rules (unknown components, duplicate boundary names, kind/type checks, `step_size ≤ communication_step`, solver/wrapper `communication_step` equality).
- **Edge wiring** — system `<Connectors>` become boundary `WrapperVariable`s (kind → causality mapping, `calculatedParameter` → readable output, `inout` → `input`); `ParameterValues` feed start values; absent connectors fall back to mapper auto-discovery (IMP-013).
- **Vendor annotation** — solver/wrapper policy (`Solver`/`AlgebraicLoop`/`Wrapper` elements on the `cs-fmu-packager` annotation) is parsed with defaults fallback, plus `--step-size`/`--communication-step` CLI overrides.
- **TOML removed** — `spec.py` and `test_spec_validation.py` deleted, `toml>=0.10` dropped from `pyproject.toml`; the `spec_file` fixture was removed.
- **Tests** — `tests/test_ssp_spec.py` (23 tests) replaces the TOML suite; `tests/helpers.py`/`conftest.py` gained `build_ssp_document`/`make_ssp`/`make_fmu_bytes` builders; the IMP-028 multi-FMU chain tests now author `.ssp` packages and exercise the full CLI build+simulate path with real OMC FMUs.
- **Docs** — `modules/spec.md` → `modules/ssp_spec.md`, `test-cases/test_spec_validation.md` → `test-cases/test_ssp_spec.md`, README/GETTING_STARTED rewritten for `.ssp` input, Trace Chain 4 and decision log updated, AD-005 marked superseded.

Full suite result: 60 passed (including IMP-028 multi-FMU chain build + fmpy simulation with real OMC FMUs and vcpkg).