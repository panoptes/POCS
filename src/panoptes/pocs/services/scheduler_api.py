from typing import Any

from astropy.time import Time
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from panoptes.pocs.scheduler import create_scheduler_from_config

app = FastAPI()

# Global scheduler instance
scheduler = None


@app.on_event("startup")
async def startup_event():
    global scheduler
    try:
        scheduler = create_scheduler_from_config()
    except Exception as e:
        print(f"Failed to create scheduler: {e}")
        scheduler = None


@app.get("/status")
def status():
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")
    return {"result": scheduler.status}


@app.get("/has_valid_observations")
def has_valid_observations():
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")
    return {"result": scheduler.has_valid_observations}


@app.get("/get_observation")
def get_observation(time: str | None = None):
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")

    t = Time(time) if time else None
    obs = scheduler.get_observation(time=t)

    if obs:
        return {"result": obs.name}
    return {"result": None}


@app.post("/clear_available_observations")
def clear_available_observations():
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")
    scheduler.clear_available_observations()
    return {"result": True}


@app.post("/reset_observed_list")
def reset_observed_list():
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")
    scheduler.reset_observed_list()
    return {"result": True}


class ObservationConfig(BaseModel):
    observation_config: dict[str, Any]


@app.post("/add_observation")
def add_observation(config: ObservationConfig):
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")
    try:
        scheduler.add_observation(config.observation_config)
        return {"result": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/remove_observation")
def remove_observation(field_name: str):
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")
    scheduler.remove_observation(field_name)
    return {"result": True}
