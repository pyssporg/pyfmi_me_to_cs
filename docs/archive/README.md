<!-- GENERATED FILE — do not edit. Regenerate with `pb registers`. -->

# Decision Stream

Flat, dated history of every committed design choice. Current state lives
in the layer leaves named by each record's `state:` field.

Records live in the cold-storage archive; extract one with `pb archive read <ID>`.

## By Layer

### Architecture

- **AD-011** — modelDescription emission moves to pyfmi_interfaces · accepted · 2026-11-22 · `AD-011`
  One emitter in pyfmi_interfaces renders the Co-Simulation modelDescription with canonical VendorAnnotations; this repo supplies the GUID, the CsFmuPackager payload, the FMI facade, and the solver, and keeps no legacy document layout.
