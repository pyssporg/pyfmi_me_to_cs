# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.1] - 2026-11-09

### Added

- First public release of `cs-fmu-packager`: package FMI 2.0 Model Exchange
  FMUs into a single Co-Simulation FMU.

### Changed

- Port FMU handling onto the `experimental_pyssp_standard` facade API and pin
  it to the v0.9.3.dev0 release wheel.
- Harden the ecosystem CI workflows, add a changelog and ruff config, and
  update the `cs_behavior` and end-to-end tests.

