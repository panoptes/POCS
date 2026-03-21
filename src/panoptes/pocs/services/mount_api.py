from contextlib import asynccontextmanager

from astropy.coordinates import SkyCoord
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from pydantic import BaseModel

from panoptes.utils.serializers import serialize_all_objects
from panoptes.pocs.mount import create_mount_from_config
from panoptes.pocs.utils.logger import get_logger

logger = get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan context manager that manages the mount instance."""
    try:
        app.state.mount = create_mount_from_config(client_mode=False)
    except Exception:
        logger.exception("Failed to create mount from config")
        app.state.mount = None
    try:
        yield
    finally:
        mount = getattr(app.state, "mount", None)
        if mount is not None:
            try:
                # Attempt a clean disconnect on shutdown.
                mount.disconnect()
            except Exception:
                logger.exception("Error while disconnecting mount during shutdown")


app = FastAPI(lifespan=lifespan)


def get_mount(request: Request):
    """Retrieve the mount instance from the FastAPI application state."""
    mount = getattr(request.app.state, "mount", None)
    if mount is None:
        raise HTTPException(status_code=503, detail="Mount not initialized")
    return mount


@app.get("/status")
def status(request: Request):
    mount = get_mount(request)
    # mount.status is a @property, so we don't call it.
    return serialize_all_objects({"result": mount.status})


@app.post("/connect")
def connect(request: Request):
    mount = get_mount(request)
    return {"result": mount.connect()}


@app.post("/initialize")
def initialize(request: Request):
    mount = get_mount(request)
    return {"result": mount.initialize()}


@app.post("/disconnect")
def disconnect(request: Request):
    mount = get_mount(request)
    return {"result": mount.disconnect()}


@app.get("/is_connected")
def is_connected(request: Request):
    mount = get_mount(request)
    return {"result": mount.is_connected}


@app.get("/is_initialized")
def is_initialized(request: Request):
    mount = get_mount(request)
    return {"result": mount.is_initialized}


@app.get("/is_parked")
def is_parked(request: Request):
    mount = get_mount(request)
    return {"result": mount.is_parked}


@app.get("/is_home")
def is_home(request: Request):
    mount = get_mount(request)
    return {"result": mount.is_home}


@app.get("/is_tracking")
def is_tracking(request: Request):
    mount = get_mount(request)
    return {"result": mount.is_tracking}


@app.get("/is_slewing")
def is_slewing(request: Request):
    mount = get_mount(request)
    return {"result": mount.is_slewing}


@app.get("/state")
def state(request: Request):
    mount = get_mount(request)
    return {"result": mount.state}


@app.get("/has_target")
def has_target(request: Request):
    mount = get_mount(request)
    return {"result": mount.has_target}


class Coordinates(BaseModel):
    coords: str


@app.post("/set_target_coordinates")
def set_target_coordinates(request: Request, coords_data: Coordinates):
    mount = get_mount(request)
    try:
        skycoord = SkyCoord(coords_data.coords)
        result = mount.set_target_coordinates(skycoord)
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/get_target_coordinates")
def get_target_coordinates(request: Request):
    mount = get_mount(request)
    coords = mount.get_target_coordinates()
    if coords:
        return {"result": coords.to_string("hmsdms")}
    return {"result": None}


@app.get("/get_current_coordinates")
def get_current_coordinates(request: Request):
    mount = get_mount(request)
    coords = mount.get_current_coordinates()
    if coords:
        return {"result": coords.to_string("hmsdms")}
    return {"result": None}


@app.post("/slew_to_target")
def slew_to_target(
    request: Request, background_tasks: BackgroundTasks, blocking: bool = False, timeout: float = 180.0
):
    mount = get_mount(request)
    if blocking:
        return {"result": mount.slew_to_target(blocking=True, timeout=timeout)}
    else:
        background_tasks.add_task(mount.slew_to_target, blocking=False, timeout=timeout)
        return {"result": True, "message": "Slewing in background"}


@app.post("/slew_to_coordinates")
def slew_to_coordinates(request: Request, coords_data: Coordinates, background_tasks: BackgroundTasks):
    mount = get_mount(request)
    try:
        skycoord = SkyCoord(coords_data.coords)
        background_tasks.add_task(mount.slew_to_coordinates, skycoord)
        return {"result": True, "message": "Slewing in background"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/slew_to_home")
def slew_to_home(
    request: Request, background_tasks: BackgroundTasks, blocking: bool = False, timeout: float = 180.0
):
    mount = get_mount(request)
    if blocking:
        return {"result": mount.slew_to_home(blocking=True, timeout=timeout)}
    else:
        background_tasks.add_task(mount.slew_to_home, blocking=False, timeout=timeout)
        return {"result": True, "message": "Slewing to home in background"}


@app.post("/park")
def park(request: Request, background_tasks: BackgroundTasks):
    mount = get_mount(request)
    background_tasks.add_task(mount.park)
    return {"result": True, "message": "Parking in background"}


@app.post("/unpark")
def unpark(request: Request):
    mount = get_mount(request)
    return {"result": mount.unpark()}


@app.post("/set_tracking_rate")
def set_tracking_rate(request: Request, direction: str = "ra", delta: float = 1.0):
    mount = get_mount(request)
    mount.set_tracking_rate(direction=direction, delta=delta)
    return {"result": True}
