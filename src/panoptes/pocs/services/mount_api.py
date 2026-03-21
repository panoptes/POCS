from astropy.coordinates import SkyCoord
from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel

from panoptes.pocs.mount import create_mount_from_config

app = FastAPI()

# Global mount instance
mount = None


@app.on_event("startup")
async def startup_event():
    global mount
    try:
        mount = create_mount_from_config()
    except Exception as e:
        print(f"Failed to create mount: {e}")
        mount = None


@app.get("/status")
def status():
    if not mount:
        raise HTTPException(status_code=503, detail="Mount not initialized")
    return mount.status()


@app.post("/connect")
def connect():
    if not mount:
        raise HTTPException(status_code=503, detail="Mount not initialized")
    return {"result": mount.connect()}


@app.post("/initialize")
def initialize():
    if not mount:
        raise HTTPException(status_code=503, detail="Mount not initialized")
    return {"result": mount.initialize()}


@app.post("/disconnect")
def disconnect():
    if not mount:
        raise HTTPException(status_code=503, detail="Mount not initialized")
    return {"result": mount.disconnect()}


@app.get("/is_connected")
def is_connected():
    if not mount:
        raise HTTPException(status_code=503, detail="Mount not initialized")
    return {"result": mount.is_connected}


@app.get("/is_initialized")
def is_initialized():
    if not mount:
        raise HTTPException(status_code=503, detail="Mount not initialized")
    return {"result": mount.is_initialized}


@app.get("/is_parked")
def is_parked():
    if not mount:
        raise HTTPException(status_code=503, detail="Mount not initialized")
    return {"result": mount.is_parked}


@app.get("/is_home")
def is_home():
    if not mount:
        raise HTTPException(status_code=503, detail="Mount not initialized")
    return {"result": mount.is_home}


@app.get("/is_tracking")
def is_tracking():
    if not mount:
        raise HTTPException(status_code=503, detail="Mount not initialized")
    return {"result": mount.is_tracking}


@app.get("/is_slewing")
def is_slewing():
    if not mount:
        raise HTTPException(status_code=503, detail="Mount not initialized")
    return {"result": mount.is_slewing}


@app.get("/state")
def state():
    if not mount:
        raise HTTPException(status_code=503, detail="Mount not initialized")
    return {"result": mount.state}


@app.get("/has_target")
def has_target():
    if not mount:
        raise HTTPException(status_code=503, detail="Mount not initialized")
    return {"result": mount.has_target}


class Coordinates(BaseModel):
    coords: str


@app.post("/set_target_coordinates")
def set_target_coordinates(coords_data: Coordinates):
    if not mount:
        raise HTTPException(status_code=503, detail="Mount not initialized")
    try:
        skycoord = SkyCoord(coords_data.coords)
        result = mount.set_target_coordinates(skycoord)
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/get_target_coordinates")
def get_target_coordinates():
    if not mount:
        raise HTTPException(status_code=503, detail="Mount not initialized")
    coords = mount.get_target_coordinates()
    if coords:
        return {"result": coords.to_string("hmsdms")}
    return {"result": None}


@app.get("/get_current_coordinates")
def get_current_coordinates():
    if not mount:
        raise HTTPException(status_code=503, detail="Mount not initialized")
    coords = mount.get_current_coordinates()
    if coords:
        return {"result": coords.to_string("hmsdms")}
    return {"result": None}


@app.post("/slew_to_target")
def slew_to_target(background_tasks: BackgroundTasks, blocking: bool = False, timeout: float = 180.0):
    if not mount:
        raise HTTPException(status_code=503, detail="Mount not initialized")
    if blocking:
        return {"result": mount.slew_to_target(blocking=True, timeout=timeout)}
    else:
        background_tasks.add_task(mount.slew_to_target, blocking=False, timeout=timeout)
        return {"result": True, "message": "Slewing in background"}


@app.post("/slew_to_coordinates")
def slew_to_coordinates(coords_data: Coordinates, background_tasks: BackgroundTasks):
    if not mount:
        raise HTTPException(status_code=503, detail="Mount not initialized")
    try:
        skycoord = SkyCoord(coords_data.coords)
        background_tasks.add_task(mount.slew_to_coordinates, skycoord)
        return {"result": True, "message": "Slewing in background"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/slew_to_home")
def slew_to_home(background_tasks: BackgroundTasks, blocking: bool = False, timeout: float = 180.0):
    if not mount:
        raise HTTPException(status_code=503, detail="Mount not initialized")
    if blocking:
        return {"result": mount.slew_to_home(blocking=True, timeout=timeout)}
    else:
        background_tasks.add_task(mount.slew_to_home, blocking=False, timeout=timeout)
        return {"result": True, "message": "Slewing to home in background"}


@app.post("/park")
def park(background_tasks: BackgroundTasks):
    if not mount:
        raise HTTPException(status_code=503, detail="Mount not initialized")
    background_tasks.add_task(mount.park)
    return {"result": True, "message": "Parking in background"}


@app.post("/unpark")
def unpark():
    if not mount:
        raise HTTPException(status_code=503, detail="Mount not initialized")
    return {"result": mount.unpark()}


@app.post("/set_tracking_rate")
def set_tracking_rate(direction: str = "ra", delta: float = 1.0):
    if not mount:
        raise HTTPException(status_code=503, detail="Mount not initialized")
    mount.set_tracking_rate(direction=direction, delta=delta)
    return {"result": True}
