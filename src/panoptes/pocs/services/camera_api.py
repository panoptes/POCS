from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import unquote

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from pydantic import BaseModel

from panoptes.utils.serializers import serialize_all_objects
from panoptes.pocs.camera import create_cameras_from_config
from panoptes.pocs.utils.logger import get_logger

logger = get_logger()


import asyncio

@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan context manager that manages the camera instances."""
    app.state.cameras = {}
    
    # Attempt to initialize hardware during startup.
    # We retry a few times in case the config server is still starting up.
    for i in range(10):
        try:
            logger.info(f"Startup attempt {i+1}/10 to create cameras.")
            cameras = create_cameras_from_config(client_mode=False) or {}
            if cameras:
                logger.info(f"Created {len(cameras)} cameras, attempting to connect.")
                for cam_name, cam in cameras.items():
                    try:
                        if not cam.is_connected:
                            cam.connect()
                        logger.success(f"Camera {cam_name} connected.")
                    except Exception as e:
                        logger.error(f"Failed to connect camera {cam_name}: {e!r}")
                app.state.cameras = cameras
                break
        except Exception as e:
            logger.warning(f"Camera creation attempt {i+1} failed: {e!r}")
            await asyncio.sleep(2)
    yield


app = FastAPI(lifespan=lifespan)


def get_cameras(request: Request):
    """Retrieve the cameras dictionary from the FastAPI application state."""
    cameras = getattr(request.app.state, "cameras", {})
    
    # If no cameras initialized, try once more lazily.
    if not cameras:
        logger.info("No cameras initialized, attempting lazy creation.")
        try:
            cameras = create_cameras_from_config(client_mode=False) or {}
            if cameras:
                for cam_name, cam in cameras.items():
                    if not cam.is_connected:
                        cam.connect()
                request.app.state.cameras = cameras
        except Exception as e:
            logger.error(f"Lazy camera creation failed: {e!r}")
            
    return cameras


def get_camera(request: Request, name: str):
    cameras = get_cameras(request)
    # Decode camera name if it was URL-encoded by the proxy
    name = unquote(name)
    cam = cameras.get(name)
    if not cam:
        raise HTTPException(status_code=404, detail=f"Camera {name} not found")
    return cam


@app.get("/cameras")
def list_cameras(request: Request):
    cameras = get_cameras(request)
    return {"result": list(cameras.keys())}


@app.get("/{name}/status")
def status(request: Request, name: str):
    cam = get_camera(request, name)
    status = {
        "uid": cam.uid,
        "is_connected": cam.is_connected,
        "is_exposing": cam.is_exposing,
        "is_ready": cam.is_ready,
        "temperature": cam.temperature,
        "target_temperature": cam.target_temperature,
        "cooling_enabled": cam.cooling_enabled,
        "cooling_power": cam.cooling_power,
    }
    return serialize_all_objects(status)


@app.post("/{name}/connect")
def connect(request: Request, name: str):
    cam = get_camera(request, name)
    cam.connect()
    return {"result": True}


@app.get("/{name}/properties")
def properties(request: Request, name: str):
    cam = get_camera(request, name)
    properties = {
        "uid": cam.uid,
        "is_connected": cam.is_connected,
        "readout_time": cam.readout_time,
        "file_extension": cam.file_extension,
        "egain": cam.egain,
        "bit_depth": cam.bit_depth,
        "temperature": cam.temperature,
        "target_temperature": cam.target_temperature,
        "temperature_tolerance": cam.temperature_tolerance,
        "cooling_enabled": cam.cooling_enabled,
        "cooling_power": cam.cooling_power,
        "filter_type": cam.filter_type,
        "is_cooled_camera": cam.is_cooled_camera,
        "is_temperature_stable": cam.is_temperature_stable,
        "is_exposing": cam.is_exposing,
        "is_ready": cam.is_ready,
        "can_take_internal_darks": cam.can_take_internal_darks,
    }
    return serialize_all_objects(properties)


class ExposureParams(BaseModel):
    seconds: float
    filename: str
    metadata: dict[str, Any] | None = None
    dark: bool = False
    blocking: bool = False
    timeout: float = 10.0


@app.post("/{name}/take_exposure")
def take_exposure(request: Request, name: str, params: ExposureParams):
    cam = get_camera(request, name)
    try:
        cam.take_exposure(
            seconds=params.seconds,
            filename=params.filename,
            metadata=params.metadata,
            dark=params.dark,
            blocking=params.blocking,
            timeout=params.timeout,
        )
        return {"result": True, "message": "Exposure started/completed"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


class ProcessParams(BaseModel):
    metadata: dict[str, Any]


@app.post("/{name}/process_exposure")
def process_exposure(request: Request, name: str, params: ProcessParams, background_tasks: BackgroundTasks):
    cam = get_camera(request, name)
    background_tasks.add_task(cam.process_exposure, params.metadata)
    return {"result": True, "message": "Processing in background"}


@app.post("/{name}/set_target_temperature")
def set_target_temperature(request: Request, name: str, target: float):
    cam = get_camera(request, name)
    cam.target_temperature = target
    return {"result": True}


@app.post("/{name}/set_cooling_enabled")
def set_cooling_enabled(request: Request, name: str, enabled: bool):
    cam = get_camera(request, name)
    cam.cooling_enabled = enabled
    return {"result": True}
