# Hardware Service Auto-Initialization Plan

## Background & Motivation
Stand-alone hardware services (Mount, Camera, Scheduler) should ideally be "ready to use" (connected and initialized) as soon as they are running. Currently, they only create the hardware instance but do not call the initialization/connection methods until a client explicitly requests it. This plan simplifies the startup by ensuring that all hardware services attempt to initialize their physical components immediately upon launch. We assume the POCS configuration server is already running, as managed by the system's process supervisor (e.g., `supervisord`).

## Proposed Changes
Update the `lifespan` of each service to not only *create* the hardware instance but also attempt to *connect* and *initialize* it.

## Implementation Details

### 1. Mount Service (`src/panoptes/pocs/services/mount_api.py`)
- **Lifespan**:
    - Call `mount = create_mount_from_config(client_mode=False)`.
    - If successful, call `mount.initialize()`.
    - Ensure `app.state.mount` is set even if `initialize()` fails, allowing for manual retries via the API.

### 2. Camera Service (`src/panoptes/pocs/services/camera_api.py`)
- **Lifespan**:
    - Call `cameras = create_cameras_from_config(client_mode=False)`.
    - Loop through all cameras and call `cam.connect()` if not already connected.

### 3. Scheduler Service (`src/panoptes/pocs/services/scheduler_api.py`)
- **Lifespan**:
    - Call `create_scheduler_from_config(client_mode=False)`. (This naturally initializes the scheduler by loading the fields file).

## Verification & Testing
- Start hardware services with simulators configured, verify logs show successful initialization.
- Verify that a client can immediately request status and receive data without needing an explicit `/initialize` call first.
