# Telemetry Server Transition Plan

This document outlines the plan for migrating POCS from the legacy `FileDB`/`MemoryDB` system to the new telemetry server available in `panoptes-utils > 0.2.55`.

## Goals
- Replace `insert_current` calls with structured telemetry posts.
- Use `pydantic` models to ensure consistent data formats for all sensors.
- Enable direct telemetry reporting to a centralized server.
- Maintain backward compatibility for local file-based logging during the transition.

## Phase 1: Environment & Dependencies
1. Update `pyproject.toml` to require `panoptes-utils>=0.2.55`.
2. Run `uv lock` and `uv sync` to update the environment.

## Phase 2: Data Modeling
1. Create `src/panoptes/pocs/utils/telemetry.py`.
2. Define `pydantic` models for:
    - `WeatherReading` (based on AAG/weather station data)
    - `PowerReading` (based on Arduino power board data)
    - `ImageMetadata` (captured during observation)
    - `ObservatoryStatus` (mount coordinates, tracking state, etc.)
    - `StateMachineState` (current/next state transitions)
    - `SafetyStatus` (combined safety flags)

## Phase 3: Infrastructure Integration
1. Update `PanBase` in `src/panoptes/pocs/base.py`:
    - Initialize `panoptes.utils.telemetry.TelemetryClient`.
    - Add a `record_telemetry` method that accepts a pydantic model instance.
    - Configuration options for telemetry server host/port.

## Phase 4: Component Refactoring
1. **Weather**: Update `src/panoptes/pocs/sensor/weather.py` to use `WeatherReading` model.
2. **Power**: Update `src/panoptes/pocs/sensor/power.py` to use `PowerReading` model.
3. **Observatory**: Update `src/panoptes/pocs/observatory.py` to record `ObservatoryStatus`.
4. **State Machine**: Update `src/panoptes/pocs/core.py` and `src/panoptes/pocs/state/machine.py` to record state transitions.
5. **Images**: Update image metadata recording during exposure completion.

## Phase 5: Testing & Validation
1. Verify with simulators that telemetry is being posted.
2. Ensure the legacy `FileDB` still receives entries if configured (optional).
3. Add unit tests for the new telemetry models and client integration.

## Phase 6: Cleanup
1. Deprecate `insert_current` for sensor data.
2. Update `upload-metadata` CLI tool or replace with telemetry-native forwarding.
