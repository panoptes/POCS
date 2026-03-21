from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel

from panoptes.pocs.camera import create_cameras_from_config

app = FastAPI()

# Global cameras dict
cameras = {}


@app.on_event("startup")
async def startup_event():
    global cameras
    try:
        cameras = create_cameras_from_config() or {}
    except Exception as e:
        print(f"Failed to create cameras: {e}")
        cameras = {}


def get_camera(name: str):
    cam = cameras.get(name)
    if not cam:
        raise HTTPException(status_code=404, detail=f"Camera {name} not found")
    return cam


@app.get("/cameras")
def list_cameras():
    return {"result": list(cameras.keys())}


@app.get("/{name}/status")
def status(name: str):
    cam = get_camera(name)
    return {
        "uid": cam.uid,
        "is_connected": cam.is_connected,
        "is_exposing": cam.is_exposing,
        "is_ready": cam.is_ready,
        "temperature": cam.temperature,
        "target_temperature": cam.target_temperature,
        "cooling_enabled": cam.cooling_enabled,
        "cooling_power": cam.cooling_power,
    }


@app.post("/{name}/connect")
def connect(name: str):
    cam = get_camera(name)
    cam.connect()
    return {"result": True}


@app.get("/{name}/properties")
def properties(name: str):
    cam = get_camera(name)
    return {
        "uid": cam.uid,
        "is_connected": cam.is_connected,
        "readout_time": cam.readout_time.value if hasattr(cam.readout_time, "value") else cam.readout_time,
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


class ExposureParams(BaseModel):
    seconds: float
    filename: str
    metadata: dict[str, Any] | None = None
    dark: bool = False
    blocking: bool = False
    timeout: float = 10.0


@app.post("/{name}/take_exposure")
def take_exposure(name: str, params: ExposureParams):
    cam = get_camera(name)
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
def process_exposure(name: str, params: ProcessParams, background_tasks: BackgroundTasks):
    cam = get_camera(name)
    background_tasks.add_task(cam.process_exposure, params.metadata)
    return {"result": True, "message": "Processing in background"}


@app.post("/{name}/set_target_temperature")
def set_target_temperature(name: str, target: float):
    cam = get_camera(name)
    cam.target_temperature = target
    return {"result": True}


@app.post("/{name}/set_cooling_enabled")
def set_cooling_enabled(name: str, enabled: bool):
    cam = get_camera(name)
    cam.cooling_enabled = enabled
    return {"result": True}
