# cs-fmu-packager — development Makefile
#
# Targets:
#   generate-fixtures   — Regenerate all test FMU fixtures from Modelica sources
#                         (requires omc / OpenModelica compiler)
#   example             — Build the runnable quickstart example SSP package
#                         (requires omc / OpenModelica compiler)

FIXTURES_DIR   = tests/fixtures
GENERATE_SCRIPT = $(FIXTURES_DIR)/generate_test_fmus.py

.PHONY: generate-fixtures
generate-fixtures:
	@echo "=== Regenerating test FMU fixtures ==="
	python3 $(GENERATE_SCRIPT) $(FIXTURES_DIR) --cs
	@echo "=== Done ==="

.PHONY: generate-fixtures-me
generate-fixtures-me:
	@echo "=== Regenerating ME-only test FMU fixtures ==="
	python3 $(GENERATE_SCRIPT) $(FIXTURES_DIR)
	@echo "=== Done ==="

.PHONY: example
example:
	@echo "=== Building runnable quickstart example ==="
	python3 examples/quickstart/build_example.py
	@echo "=== Done ==="