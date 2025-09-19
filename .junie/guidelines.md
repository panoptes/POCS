# Project Guidelines for PANOPTES POCS

Last updated: 2025-09-18

Project home: https://github.com/panoptes/POCS
Documentation: https://pocs.readthedocs.io

1) Project Overview
- PANOPTES is an open-source citizen science project to discover transiting exoplanets using a global network of robotic, DSLR-based telescopes.
- POCS (PANOPTES Observatory Control System) is the main software driver for a PANOPTES unit. It provides high-level orchestration of hardware (cameras, mounts, domes, sensors), scheduling, and state-machine based operations. The package can run fully simulated for development and testing.

2) Repository Layout (high-level)
- src/panoptes/pocs: Main Python package source.
  - camera, mount, dome, focuser, filterwheel, scheduler, sensor, state, utils: Feature areas.
- tests: Unit and integration tests for package modules.
- conf_files: Default configuration files (e.g., pocs.yaml, state tables, fields).
- resources: Vendor/device resources, scripts, and binaries (excluded from tests/linters).
- docs: Documentation assets.
- notebooks: Example notebooks (not used by CI).
- pyproject.toml: Build system, dependencies, pytest and ruff configuration.
- README.md: Project intro, install and basic usage.

3) Python and Tooling
- Python: 3.12 only (see project.classifiers and tool.ruff target-version).
- Build backend: Hatchling (pyproject [build-system]).
- CLI entry point: pocs → panoptes.pocs.utils.cli.main:app (Typer-based CLI).

4) How Junie should run tests
- Run tests only for the files that have changed.
- Recommended environment setup:
  1. Create/activate a virtual environment for Python 3.12.
  2. Install the package with testing extras:
     pip install -e .[testing]
  3. Run the test suite (pytest options are preconfigured in pyproject):
     pytest
- Notes:
  - Tests run against both src and tests paths (see pytest.ini options in pyproject).
  - Coverage reports are generated to build/coverage.xml and terminal (skip-covered enabled).
  - Some tests are marked for specific hardware; you can select markers as needed, e.g.: pytest -m "without_camera and without_mount".

5) Linting and Formatting
- Ruff is configured via pyproject with line-length 100 and target Python 3.12.
- Common commands (via hatch env scripts if hatch is installed):
  - hatch run lint        # ruff check .
  - hatch run lint-fix    # ruff check --fix .
  - hatch run fmt         # ruff format .
  - hatch run fmt-check   # ruff format --check .
- If hatch is unavailable, run ruff directly once installed: ruff check . and ruff format .

6) Building (optional for most changes)
- Wheel build with Hatchling:
  - pip install build
  - python -m build
- Or using hatch:
  - hatch build

7) Minimal contribution guidance for Junie
- Prefer minimal diffs focused on the stated issue.
- Keep public APIs stable unless the issue requires changes; update tests accordingly.
- Follow existing code patterns in src/panoptes/pocs and respect module boundaries.
- Add or adjust tests when behavior changes.
- Ensure tests and ruff checks pass before submitting.
- Docstrings should be in Google python style.

8) Useful links
- Project overview: https://projectpanoptes.org/articles/
- PANOPTES Utils (config server used by POCS): https://github.com/panoptes/panoptes-utils
