# AD-005: TOML Spec Format

## Status

Accepted

## Layer

Architecture

## Context

The package specification must be a declarative text format suitable for version control. Candidates were: TOML, YAML, JSON, and SSP-derived XML.

- **JSON** is widely supported but lacks comments and inline documentation.
- **YAML** is human-readable but has complex syntax rules and security concerns (arbitrary code execution via `!!python/object`).
- **SSP XML** is a standard but verbose and requires namespace handling.
- **TOML** is human-readable, supports comments, is well-defined, and maps naturally to Python dataclasses.

The project's requirements (SPR-001 through SPR-007) emphasize readability, version-control friendliness, and explicit declaration of FMU references, connections, and solver policies.

## Decision

Use **TOML** as the package specification format. Do not support YAML or any other format in v1.

## Alternatives Considered

- JSON — lacks comments, which are valuable for self-documenting specs.
- YAML — security concerns and complex edge cases.
- SSP XML — too verbose for v1; may be considered for future import/export.

## Consequences

- **Positive:** Clean, readable syntax with comment support.
- **Positive:** Standard Python `toml` library provides simple parsing.
- **Positive:** No security concerns (unlike YAML's arbitrary code execution).
- **Negative:** TOML is less familiar than JSON for some users.
- **Negative:** Not a standard simulation interchange format (unlike SSP).

## Affected Artifacts

- `03-implementation/modules/spec.md` — TOML parser and validator
- `03-implementation/modules/models.md` — `PackageSpec` and related dataclasses
- `04-verification/test-cases/test_spec_validation.md` — spec validation test fixtures

## Verification

- A valid TOML spec file parses without errors and produces a correct `PackageSpec`.
- Invalid TOML or missing sections produce clear error messages.
- The spec validates all field constraints before any FMU inspection begins.

## Review Trigger

- If standard simulation interchange formats (SSP, FMI SSP) gain widespread adoption and users request direct import/export.