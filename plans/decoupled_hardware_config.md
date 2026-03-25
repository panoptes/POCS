# Decoupled Hardware Configuration Plan

## Background & Motivation
Currently, using decoupled hardware services requires managing two separate configuration viewpoints: one for the FastAPI hardware service (which needs the physical driver, e.g., `hae16`) and one for the POCS instance (which needs the `remote` driver). On a single-machine deployment (like an RPi5), managing multiple configurations or complex environment overrides is cumbersome and error-prone. The goal is to make this process entirely transparent to the end user by using a single config file.

## Proposed Solution: The `client_mode` Flag
We will allow users to define their hardware normally in the config and simply add an `endpoint_url` to enable remote proxying. 

Example `pocs.yaml` for a mount:
```yaml
mount:
  brand: ioptron
  driver: panoptes.pocs.mount.ioptron.hae16
  serial:
    port: /dev/ttyUSB0
  endpoint_url: http://localhost:8001
```

To achieve this, we will introduce context-awareness into the hardware creation factories:

1. **Update Factory Functions**: Add a `client_mode: bool = True` parameter to `create_mount_from_config`, `create_cameras_from_config`, and `create_scheduler_from_config`.
    - **POCS Context (`client_mode=True`)**: If the factory detects an `endpoint_url` in the config, it intercepts the creation and dynamically loads the `remote` proxy driver instead of the physical driver. If no `endpoint_url` is present, it acts normally (loads the physical driver).
    - **Service Context (`client_mode=False`)**: The factory completely ignores the `endpoint_url` and instantiates the physical hardware driver (e.g., `hae16`).

2. **Update FastAPI Services**: Modify the `lifespan` context managers in `mount_api.py`, `camera_api.py`, and `scheduler_api.py` to initialize their hardware with `client_mode=False`.

## Implementation Steps

1. **Mount (`src/panoptes/pocs/mount/__init__.py`)**:
   - Update `create_mount_from_config(mount_info=None, earth_location=None, *, client_mode=True, **kwargs)`
   - Add logic: `if client_mode and "endpoint_url" in mount_info: driver = "panoptes.pocs.mount.remote"`

2. **Cameras (`src/panoptes/pocs/camera/__init__.py`)**:
   - Update `create_cameras_from_config(config=None, *, client_mode=True, **kwargs)`
   - Add logic within the loop: `if client_mode and "endpoint_url" in cam_config: cam_config["driver"] = "panoptes.pocs.camera.remote"; cam_config["model"] = "remote"`

3. **Scheduler (`src/panoptes/pocs/scheduler/__init__.py`)**:
   - Update `create_scheduler_from_config(config=None, observer=None, *, client_mode=True)`
   - Add logic: `if client_mode and "endpoint_url" in scheduler_config: scheduler_config["type"] = "panoptes.pocs.scheduler.remote"`

4. **Services (`src/panoptes/pocs/services/*_api.py`)**:
   - Update the `lifespan` blocks to explicitly pass `client_mode=False` when calling the creation factories.

## Alternatives Considered
- **Config Stripping in Lifespan**: Instead of changing the factories, the FastAPI services could fetch the config, `pop("endpoint_url")`, and pass the modified dict. This is slightly more brittle (especially for nested structures like `cameras.devices`) and less explicit than a formal `client_mode` parameter.

## Verification & Testing
- Unit tests will be updated/added to ensure `create_*_from_config(client_mode=True)` returns a remote proxy when an endpoint is present.
- Unit tests will verify `create_*_from_config(client_mode=False)` returns the physical hardware mock/simulator even when an endpoint is present.
