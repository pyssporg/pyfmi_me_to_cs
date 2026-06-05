# Product Breakdown Structure — cs-fmu-packager

This directory contains the product breakdown structure (PBS) for the cs-fmu-packager project. It organizes product knowledge into seven layers, from intent through evolution, with traceability throughout.

## Layer Index

| # | Layer | Description | Main Question |
| --- | --- | --- | --- |
| 00 | `00-intent/` | Purpose, users, outcomes, constraints, assumptions | Why does this product exist? |
| 01 | `01-product/` | Scope, capabilities, use cases, requirements, domain model, glossary | What should it do? |
| 02 | `02-architecture/` | Quality attributes, views (context, component, data, integration, deployment), decisions | How is it structurally organized? |
| 03 | `03-implementation/` | Code structure, modules, interfaces, configuration, environments | How is it built in code and configuration? |
| 04 | `04-verification/` | Test strategy, test cases, traceability matrix, acceptance criteria | How do we know it works? |
| 05 | `05-operation/` | Deployment process, runbook, monitoring, support model | What operational behavior and support constraints must the product satisfy? |
| 06 | `06-evolution/` | Risks, changelog, improvement candidates | How should it change over time? |

## Usage Guide

- **Navigating intent → verification**: Start with `00-intent/purpose.md`, then follow layer IDs down through product, architecture, implementation, and verification.
- **Finding a decision**: Check `decision-log.md` for the index, then open the full decision in the owning layer's `decisions/` directory.
- **Tracing requirements → tests**: Use `04-verification/traceability-matrix.md` for requirement-to-test mapping, or `traceability-map.md` for full cross-layer chains.
- **Understanding a module**: Find its `03-implementation/modules/<name>.md` file, which links to source code and tests.

## Boundary Rules

- **No duplication**: Content in `product-breakdown/` is the authoritative source for product knowledge. Runnable guides, command examples, install steps, and contributor workflow belong in `docs/`. If a guide needs product context, link to PBS artifacts. If a PBS artifact needs practical steps, state the durable requirement and link to `docs/`.
- **Decision placement**: A decision belongs in the layer where its consequences are most directly felt. Decisions are stored beside the artifacts they constrain. The root `decision-log.md` is only an index.

## Links

- [Decision Log](decision-log.md)
- [Traceability Map](traceability-map.md)