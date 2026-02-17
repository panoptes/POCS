# POCS - GitHub Copilot Quick Reference

> **📖 IMPORTANT:** See [`AGENTS.md`](../AGENTS.md) for comprehensive guidelines, architecture details, hardware documentation, and development processes.

## Essential Commands

```bash
# Setup (first time)
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync --all-extras --group dev

# Development cycle
uv run pytest                    # Run all tests
uv run ruff check .              # Lint
uv run ruff format .             # Format
uv build                         # Build package

# Before every commit (CI will fail without these)
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

## Code Standards Checklist

- ✅ Python 3.12+ with type hints
- ✅ Google-style docstrings
- ✅ Line length: 110 chars
- ✅ Update `CHANGELOG.md` for all PRs

## Quick Navigation

```
src/panoptes/pocs/
├── core.py          # State machine (the brain)
├── observatory.py   # Hardware coordinator
├── scheduler/       # Observation scheduler
├── camera/          # Camera drivers
├── mount/           # Telescope mount drivers
├── dome/            # Dome control
├── focuser/         # Focus control
└── utils/           # Utilities and CLI
```

## Critical Info

**Config Server:** Port 6563 (must be running)  
**Test Config:** `tests/testing.yaml`  
**State Machine:** Understand state flow before modifying `core.py`  
**Timing:** Tests may take several minutes

## Need More Info?

| Topic | See |
|-------|-----|
| Architecture | AGENTS.md → "Architecture Guidelines" |
| State machine | AGENTS.md → "State Machine (POCS Core)" |
| Hardware drivers | AGENTS.md → "Hardware Drivers" |
| Testing strategy | AGENTS.md → "Testing Requirements" |
| Configuration | AGENTS.md → "Configuration" |
| All details | **[AGENTS.md](../AGENTS.md)** ← Read this first |
