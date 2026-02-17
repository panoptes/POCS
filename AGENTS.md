# AI Agent Guidelines for POCS

This document provides guidelines for AI coding agents working with the PANOPTES Observatory Control System (POCS) codebase. It is designed to be tool-agnostic and applicable to any AI assistant working on this project.

## Project Overview

POCS (PANOPTES Observatory Control System) is the main software driver for robotic astronomical observatories designed to detect transiting exoplanets. The system controls telescope hardware, schedules observations, captures images, and manages the entire observation workflow through a state machine architecture.

**Key Characteristics:**
- **Language:** Python 3.12+ (type hints expected)
- **Architecture:** State machine-based observatory control
- **Domain:** Astronomy, robotics, hardware control
- **Testing:** pytest with high coverage requirements
- **Package Manager:** uv (modern Python package manager)
- **Code Style:** Ruff for linting and formatting

## Essential Reading

Before making changes, review these documents:

1. **Architecture:** `docs/architecture-for-beginners.md` - Understand the layered architecture
2. **Contributing:** `CONTRIBUTING.md` - Development workflow and standards
3. **CLI Guide:** `docs/cli-guide.md` - Command-line interface reference
4. **Glossary:** `docs/glossary.md` - Domain-specific terminology
5. **Conceptual Overview:** `docs/conceptual-overview.md` - High-level system design

## Project Structure

```
POCS/
├── src/panoptes/pocs/          # Main source code
│   ├── core.py                 # POCS state machine (the brain)
│   ├── observatory.py          # Hardware coordinator
│   ├── scheduler/              # Observation scheduler
│   ├── camera/                 # Camera drivers
│   ├── mount/                  # Telescope mount drivers
│   ├── dome/                   # Dome control
│   ├── focuser/                # Focus control
│   └── utils/                  # Utilities and CLI
├── tests/                      # Test suite
├── conf_files/                 # Configuration files
├── docs/                       # Documentation
└── examples/                   # Example scripts
```

## Development Workflow

### 1. Understanding Changes

**Before making any changes:**
- Check if an issue exists for the change; reference it in commits/PRs
- Read relevant architecture documentation to understand affected components
- Review existing tests to understand expected behavior
- Check `pyproject.toml` for dependencies and project configuration

### 2. Code Standards

**Style and Formatting:**
- Use Ruff for linting and formatting (configured in `pyproject.toml`)
- Line length: 110 characters
- Quote style: double quotes
- Follow PEP 8 conventions

**Type Hints:**
- Required for all function signatures
- Use modern Python 3.12+ type syntax
- Import from `typing` when necessary

**Documentation:**
- Docstrings for all public classes and functions
- Use Google-style docstrings
- Include examples in docstrings when helpful

### 3. Testing Requirements

**All code changes must include tests:**
- Unit tests in `tests/` directory
- Test files named `test_*.py`
- Use pytest fixtures from `conftest.py`
- Maintain or improve code coverage
- Run tests locally before committing: `pytest`

**Testing markers available:**
```python
@pytest.mark.theskyx          # Tests requiring TheSkyX
@pytest.mark.with_camera      # Tests requiring camera hardware
@pytest.mark.without_camera   # Tests that should skip camera
@pytest.mark.plate_solve      # Tests requiring plate solving
```

### 4. Dependencies

**Adding Dependencies:**
- Add to `dependencies` in `pyproject.toml` for runtime requirements
- Add to `[dependency-groups]` for development/testing tools
- Use `uv add <package>` to install and update lockfile
- Pin security-sensitive packages (e.g., `certifi>=2024.2.2`)

**Optional Dependencies:**
- `focuser`: Matplotlib and focus-related tools
- `google`: Google Cloud integration
- `weather`: Weather station support
- `all`: All optional features

### 5. Making Changes

**File Editing Best Practices:**
1. Read entire files or large sections before editing
2. Preserve existing code style and patterns
3. Make minimal, focused changes
4. Validate changes by checking for errors after editing
5. Run relevant tests to confirm functionality

**Commit Messages:**
- Clear, descriptive commit messages
- Reference issue numbers when applicable
- Format: `Brief description (#issue-number)`

## Architecture Guidelines

### State Machine (POCS Core)

**Location:** `src/panoptes/pocs/core.py`

The POCS state machine orchestrates observations. Key states include:
- `sleeping` → `ready` → `scheduling` → `slewing` → `tracking` → `observing` → `parking`

**When modifying:**
- Understand state transitions (defined by `transitions` library)
- Respect the state flow logic
- Add appropriate state validation
- Update state documentation if adding new states

### Scheduler Component

**Location:** `src/panoptes/pocs/scheduler/`

The scheduler decides WHAT to observe (POCS decides WHEN).

**When modifying:**
- Understand constraints system
- Preserve target selection logic
- Test with various constraint combinations
- Consider edge cases (no targets available, moon constraints, etc.)

### Observatory Coordinator

**Location:** `src/panoptes/pocs/observatory.py`

Manages all hardware as a unified system.

**When modifying:**
- Ensure thread safety for hardware access
- Validate hardware initialization sequences
- Handle missing hardware gracefully (simulator mode)
- Update hardware configuration documentation

### Hardware Drivers

**Locations:** `camera/`, `mount/`, `dome/`, `focuser/`

Device-specific control code.

**When modifying:**
- Maintain consistent driver interfaces
- Include simulator implementations for testing
- Handle hardware errors gracefully
- Add appropriate timeout handling
- Document device-specific quirks

## Configuration

**Configuration files:** `conf_files/pocs.yaml` (and variants)

**Important configuration sections:**
- `simulator`: Which components to simulate
- `mount`: Mount type and configuration
- `cameras`: Camera definitions and parameters
- `scheduler`: Field lists and constraints
- `directories`: Data storage locations

### Config Server

POCS uses a configuration server from the [`panoptes-utils`](https://github.com/panoptes/panoptes-utils) library to manage configuration. The server provides centralized configuration access across components.

**Starting the config server locally:**
```bash
# For normal development
panoptes-config-server --host 0.0.0.0 --port 6563 run --config-file conf_files/pocs.yaml

# For testing (use testing config)
panoptes-config-server --host 0.0.0.0 --port 6563 run --config-file tests/testing.yaml
```

**Notes:**
- The config server must be running before starting POCS
- Default port is 6563
- Use `tests/testing.yaml` as the config file when running tests
- The server provides a REST API for configuration access

**When modifying configuration:**
- Maintain backward compatibility when possible
- Update example configs in `conf_files/`
- Document new configuration options
- Validate with schema if available
- Restart config server after modifying config files

## Common Tasks

### Adding a New Hardware Driver

1. Create class in appropriate directory (`camera/`, `mount/`, etc.)
2. Inherit from base class (e.g., `AbstractCamera`, `AbstractMount`)
3. Implement all abstract methods
4. Create simulator version for testing
5. Add configuration options to `pocs.yaml`
6. Write comprehensive tests
7. Update documentation

### Adding a State Machine State

1. Review `core.py` state definitions
2. Add state to `transitions` configuration
3. Implement state entry/exit methods
4. Update state diagram documentation
5. Add tests for new state transitions
6. Consider error handling and recovery

### Adding CLI Commands

**Location:** `src/panoptes/pocs/utils/cli/`

1. Add command to appropriate CLI module
2. Use `typer` for command definition
3. Add help text and examples
4. Test command functionality
5. Update `docs/cli-guide.md`

### Creating a Release

**This process should be followed to create a new release of POCS.**

**Prerequisites:**
- Ensure you have write access to the repository
- Ensure all CI tests are passing on `develop` branch
- Determine the new version number (see Version Numbering below)

**Version Numbering:**
- Use semantic versioning: `vX.Y.Z`
- Get the current version: `git describe --tags --abbrev=0`
- Increment appropriately:
  - **X (Major):** Breaking changes
  - **Y (Minor):** New features, backward compatible
  - **Z (Patch):** Bug fixes, backward compatible

**Release Process:**

1. **Ensure `develop` is clean:**
   ```bash
   git checkout develop
   git pull origin develop
   git status  # Should show "nothing to commit, working tree clean"
   ```

2. **Determine version number:**
   ```bash
   # Get current version
   CURRENT_VERSION=$(git describe --tags --abbrev=0)
   echo "Current version: $CURRENT_VERSION"
   
   # Set new version (example: v0.8.10 -> v0.8.11)
   NEW_VERSION="v0.8.11"  # Update as appropriate
   echo "New version: $NEW_VERSION"
   ```

3. **Create release branch:**
   ```bash
   git checkout -b release-${NEW_VERSION} origin/develop
   ```

4. **Update `CHANGELOG.md`:**
   - Add release header with version and date: `## X.Y.Z - YYYY-MM-DD`
   - Ensure all changes are documented under appropriate sections (Added, Changed, Fixed, Removed)
   - Move any "Unreleased" changes under the new version
   - Verify all PR numbers are referenced
   - Example:
     ```markdown
     ## 0.8.11 - 2026-02-13
     
     ### Added
     - New feature description. #123
     
     ### Fixed
     - Bug fix description. #124
     ```

5. **Commit changelog updates:**
   ```bash
   git add CHANGELOG.md
   git commit -m "Update CHANGELOG for ${NEW_VERSION}"
   ```

6. **Merge release branch into `main`:**
   ```bash
   git checkout main
   git pull origin main
   git merge --no-ff release-${NEW_VERSION} -m "Merge release-${NEW_VERSION}"
   ```

7. **Resolve conflicts if necessary:**
   - If conflicts occur, resolve them carefully
   - Ensure `CHANGELOG.md` and `pyproject.toml` are correct
   - Commit resolved conflicts:
     ```bash
     git add .
     git commit -m "Resolve merge conflicts for ${NEW_VERSION}"
     ```

8. **Test and build on `main`:**
   ```bash
   # Ensure environment is up to date
   uv sync --all-extras --group dev
   
   # Run all tests (allow 5-10 minutes)
   uv run pytest
   
   # Check code style
   uv run ruff check .
   uv run ruff format --check .
   
   # Build the package
   uv build
   ```

9. **Verify distribution files:**
   ```bash
   # Check the built distribution files
   uv run --with twine twine check dist/*
   
   # Should show: "Checking dist/panoptes_pocs-X.Y.Z.tar.gz: PASSED"
   # and "Checking dist/panoptes_pocs-X.Y.Z-py3-none-any.whl: PASSED"
   ```

10. **Tag `main` with new version:**
    ```bash
    git tag -a ${NEW_VERSION} -m "Release ${NEW_VERSION}"
    ```

11. **Push `main` and tags to origin:**
    ```bash
    git push origin main
    git push origin ${NEW_VERSION}
    ```

12. **Merge release branch into `develop`:**
    ```bash
    git checkout develop
    git pull origin develop
    git merge --no-ff release-${NEW_VERSION} -m "Merge release-${NEW_VERSION} into develop"
    ```

13. **Tag `develop` with next development version:**
    ```bash
    # Set next development version (example: v0.8.11 -> v0.8.12.dev0)
    NEXT_DEV_VERSION="v0.8.12.dev0"
    git tag -a ${NEXT_DEV_VERSION} -m "Start development for ${NEXT_DEV_VERSION}"
    ```

14. **Push `develop` and tags to origin:**
    ```bash
    git push origin develop
    git push origin ${NEXT_DEV_VERSION}
    ```

15. **Clean up release branch:**
    ```bash
    git branch -d release-${NEW_VERSION}
    ```

**Post-Release:**
- Verify the new tag appears on GitHub releases page
- Monitor CI/CD for any issues
- Confirm the GitHub Actions workflow has successfully built and published the release to PyPI (triggered on tag push)
- Announce release on forum/communications channels

**Common Issues:**
- **Merge conflicts:** Most common in `CHANGELOG.md`. Keep both sets of changes and organize chronologically.
- **Test failures:** Fix on the release branch before merging to `main`.
- **Twine check failures:** Usually due to missing or malformed metadata in `pyproject.toml`.

**Automation Notes for AI Agents:**
- Parse version from `git describe --tags --abbrev=0`
- Calculate next version based on changelog entries or commit messages
- Extract date automatically: `date +%Y-%m-%d`
- Validate version format matches `vX.Y.Z` pattern
- Ensure CHANGELOG has proper section headers before merging
- Verify all tests pass before tagging

## Error Handling

**Best Practices:**
- Use specific exception types
- Provide informative error messages
- Log errors appropriately (use `loguru`)
- Clean up resources in error cases
- Consider recovery strategies
- Don't silently catch exceptions

## Logging

**The project uses `loguru` for logging, with `PanBase` providing logger setup:**

Most classes inherit from `PanBase`, which automatically sets up a logger:
```python
class MyClass(PanBase):
    def my_method(self):
        self.logger.info("Informational message")
        self.logger.warning("Warning message")
        self.logger.error("Error message")
        self.logger.debug("Debug details")
```

For standalone utilities or modules that don't inherit from `PanBase`:
```python
from loguru import logger

logger.info("Informational message")
```

**Guidelines:**
- Use `self.logger` in classes that inherit from `PanBase`
- Import `logger` from `loguru` only for standalone utilities
- Log important state changes
- Include context in log messages
- Use appropriate log levels
- Don't log sensitive information
- Consider log volume (avoid spam)

## Testing Strategy

### Test Organization

```
tests/
├── test_*.py              # Main test files
├── conftest.py            # Pytest configuration and fixtures
├── testing.yaml           # Test configuration
├── data/                  # Test data files
└── utils/                 # Test utilities
```

### Writing Tests

**Good test characteristics:**
- Isolated (don't depend on other tests)
- Repeatable (same result every time)
- Fast (use simulators, not real hardware)
- Clear (obvious what's being tested)
- Comprehensive (test edge cases)

**Use fixtures:**
```python
def test_camera_exposure(camera):
    """Test camera can take exposure."""
    # Use camera fixture from conftest.py
```

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_camera.py

# Run specific test
pytest tests/test_camera.py::test_camera_exposure

# Run with markers
pytest -m "not with_camera"

# Run with coverage
pytest --cov=panoptes.pocs
```

## Documentation

### Docstring Format (Google Style)

```python
def function_name(param1: str, param2: int) -> bool:
    """Brief one-line description.
    
    Longer description if needed. Explain what the function does,
    why it exists, and any important details.
    
    Args:
        param1: Description of param1
        param2: Description of param2
        
    Returns:
        Description of return value
        
    Raises:
        ValueError: When this happens
        RuntimeError: When that happens
        
    Examples:
        >>> function_name("test", 42)
        True
    """
```

### Documentation Updates

When making changes, update:
- Inline code comments for complex logic
- Docstrings for API changes
- Architecture docs for structural changes
- CLI guide for new commands
- Examples for new features
- Changelog (`CHANGELOG.md`) for notable changes

## Security Considerations

- Pin security-sensitive dependencies
- Validate external input (coordinates, file paths, etc.)
- Handle credentials securely (never commit secrets)
- Sanitize user-provided configuration
- Consider physical safety (hardware commands)
- Validate astronomical calculations (safety limits)

## Performance Considerations

- Observatory control is real-time critical
- Avoid blocking operations in main loop
- Use appropriate timeout values
- Consider hardware response times
- Monitor resource usage (disk, memory)
- Optimize image processing pipelines

## Common Pitfalls

1. **Simulator vs. Real Hardware:** Always test with simulators first
2. **Thread Safety:** Hardware access must be thread-safe
3. **State Machine Flow:** Don't bypass state transitions
4. **Configuration Validation:** Validate config before use
5. **Resource Cleanup:** Always clean up hardware connections
6. **Astropy Units:** Use units consistently (especially angles)
7. **Time Zones:** Use UTC for all astronomical calculations
8. **Path Handling:** Use `pathlib.Path`, handle both absolute and relative paths

## Astronomy Domain Knowledge

**Key concepts to understand:**
- **Alt/Az vs. RA/Dec:** Different coordinate systems
- **Sidereal Time:** Astronomical time standard
- **Transit:** When object crosses meridian
- **Airmass:** Atmospheric thickness (affects observations)
- **Field of View:** Area of sky visible to camera
- **Plate Solving:** Determining image coordinates from stars
- **Light Frames:** Science images
- **Dark/Flat/Bias Frames:** Calibration images

**Useful libraries:**
- **`panoptes-utils`**: **Primary source for PANOPTES utilities** - Always check here first for common functionality (time utilities, configuration, logging setup, etc.) before implementing new utilities or importing external libraries
- `astropy`: Astronomical calculations and units
- `astroplan`: Observation planning
- `astroquery`: Catalog queries

## Getting Help

- **Documentation:** https://pocs.readthedocs.io
- **Forum:** https://forum.projectpanoptes.org
- **Issues:** https://github.com/panoptes/POCS/issues
- **Code of Conduct:** `CODE_OF_CONDUCT.md`

## AI Agent-Specific Tips

### Context Gathering

1. **Start broad, then narrow:**
   - Read architecture docs first
   - Understand component relationships
   - Then dive into specific files

2. **Search effectively:**
   - Use semantic search for concepts
   - Use grep for specific strings/patterns
   - Check test files for usage examples

3. **Understand before changing:**
   - Read the full function/class
   - Check call sites to understand usage
   - Review related tests

### Making Changes

1. **Validate assumptions:**
   - Check current behavior with tests
   - Verify understanding of requirements
   - Consider edge cases

2. **Incremental approach:**
   - Make small, testable changes
   - Run tests frequently
   - Fix errors as they appear

3. **Preserve intent:**
   - Maintain existing patterns
   - Don't over-engineer solutions
   - Keep changes focused

### Communication

1. **Be specific:**
   - Reference exact file paths
   - Quote relevant code sections
   - Explain reasoning for changes

2. **Show your work:**
   - Explain what you searched for
   - Describe what you found
   - Outline your approach

3. **Ask when uncertain:**
   - Clarify requirements if ambiguous
   - Confirm understanding of domain concepts
   - Request feedback on approach

## Quick Reference

### Common Commands

```bash
# Start config server (required before running POCS)
panoptes-config-server --host 0.0.0.0 --port 6563 run --config-file conf_files/pocs.yaml

# Start config server for testing
panoptes-config-server --host 0.0.0.0 --port 6563 run --config-file tests/testing.yaml

# Install dependencies
uv sync

# Run tests
uv run pytest

# Run specific test file
uv run pytest tests/test_camera.py

# Check code style
uv run ruff check .

# Format code
uv run ruff format .

# Run POCS simulator
uv run pocs simulator

# View CLI help
uv run pocs --help
```

### File Locations

- Main POCS class: `src/panoptes/pocs/core.py`
- Observatory: `src/panoptes/pocs/observatory.py`
- Scheduler: `src/panoptes/pocs/scheduler/`
- Config: `conf_files/pocs.yaml`
- Tests: `tests/`
- CLI: `src/panoptes/pocs/utils/cli/`

### Important Conventions

- Use `self.logger` in classes inheriting from `PanBase`
- Use `pathlib.Path` for file paths
- Use `astropy.units` for physical quantities
- Use type hints on all functions
- Write tests for all new code
- Update documentation for API changes

---

**Remember:** POCS controls real hardware that moves physical equipment. Always test thoroughly and consider safety implications of changes.
