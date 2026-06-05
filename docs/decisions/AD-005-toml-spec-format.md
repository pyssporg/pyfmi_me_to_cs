# AD-005: TOML Spec Format

**Status:** Accepted

## Context

The package specification must be a declarative text format suitable for version control. Candidates were: TOML, YAML, JSON, and SSP-derived XML.

- **JSON** is widely supported but lacks comments and inline documentation.
- **YAML** is human-readable but has complex syntax rules and security concerns (arbitrary code execution via `!!python/object`).
- **SSP XML** is a standard but verbose and requires namespace handling.
- **TOML** is human-readable, supports comments, is well-defined, and maps naturally to Python dataclasses.

The project's requirements (SPR-001 through SPR-007) emphasize readability, version-control friendliness, and explicit declaration of FMU references, connections, and solver policies.

## Decision

Use **TOML** as the package specification format. Do not support YAML or any other format in v1.

## Consequences

- **Positive:** Clean, readable syntax with comment support.
- **Positive:** Standard Python `toml` library provides simple parsing.
- **Positive:** No security concerns (unlike YAML's arbitrary code execution).
- **Negative:** TOML is less familiar than JSON for some users.
- **Negative:** Not a standard simulation interchange format (unlike SSP).

## Affected Artifacts

- `src/cs_fmu_packager/spec.py` — TOML parser and validator
- `src/cs_fmu_packager/models.py` — `PackageSpec` and related dataclasses
- Tests — spec validation test fixtures