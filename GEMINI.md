# Gemini CLI Mandates for POCS

This file establishes foundational mandates for Gemini CLI when working on the PANOPTES Observatory Control System (POCS).

## Primary Directive

**All instructions and guidelines defined in [AGENTS.md](./AGENTS.md) are absolute mandates.** 

Gemini CLI must rigorously adhere to the standards, workflows, and architectural principles detailed in `AGENTS.md`, including but not limited to:

- **Code Style:** Use Ruff for linting and formatting. Use double quotes and 110-character line limits.
- **Type Safety:** Python 3.12+ type hints are required for all function signatures.
- **Documentation:** Use Google-style docstrings for all public classes and functions. All documentation must be written in Markdown for MkDocs. Do not use reStructuredText (.rst) or Sphinx.
- **Testing:** Every change MUST include corresponding `pytest` tests. Maintain high coverage.
- **Package Management:** Use `uv` for all dependency and environment management.
- **Logging:** Use `loguru` via `self.logger` (from `PanBase`) or direct import for standalone utilities.
- **Configuration:** The `panoptes-utils config` server MUST be running for POCS or its tests to function correctly.

## Project-Specific Workflow Mandates

- **Changelog Requirement:** A `CHANGELOG.md` entry is required for **every feature or bug fix**. All entries must be added under an `## [Unreleased]` section at the top of the file. Minor changes (e.g., documentation tweaks, internal refactoring) do not necessarily require a changelog entry.
- **Commit Message Format:** Use the format `Brief description (#issue-number)`.
- **Utility Preference:** ALWAYS check the [`panoptes-utils`](https://github.com/panoptes/panoptes-utils) library for existing functionality before implementing new utilities or importing external libraries.
- **Simulator-First Testing:** POCS controls physical hardware. Always prioritize safety and use simulators for verification. Never bypass state machine transitions. Use the `--simulator` flag or appropriate configuration to ensure no real hardware commands are sent during development and testing.

## Research & Validation Commands

- **Research:** Use `grep_search` to find existing implementations of similar logic to ensure architectural consistency.
- **Linting & Formatting:** 
    - `uv run ruff check .`
    - `uv run ruff format --check .` (use `uv run ruff format .` to fix)
- **Testing:** 
    - `uv run pytest <test_path>`
    - Always ensure the config server is running (usually on port 6563) before starting tests.

## Reference Documents

- **Architecture:** `docs/architecture-for-beginners.md`
- **Contributing:** `CONTRIBUTING.md`
- **Glossary:** `docs/glossary.md`
- **CLI Guide:** `docs/cli-guide.md`
