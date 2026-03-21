from contextlib import asynccontextmanager
from typing import Any

from astropy.time import Time
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

from panoptes.utils.serializers import serialize_all_objects
from panoptes.pocs.scheduler import create_scheduler_from_config
from panoptes.pocs.utils.logger import get_logger

logger = get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan context manager that manages the scheduler instance."""
    try:
        app.state.scheduler = create_scheduler_from_config()
    except Exception:
        logger.exception("Failed to create scheduler from config")
        app.state.scheduler = None
    yield


app = FastAPI(lifespan=lifespan)


def get_scheduler(request: Request):
    """Retrieve the scheduler instance from the FastAPI application state."""
    scheduler = getattr(request.app.state, "scheduler", None)
    if scheduler is None:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")
    return scheduler


@app.get("/status")
def status(request: Request):
    scheduler = get_scheduler(request)
    # scheduler.status contains live objects, so we return a subset for JSON serialization.
    status = {
        "num_observations": len(scheduler.observations),
        "has_valid_observations": scheduler.has_valid_observations,
        "current_observation": scheduler.current_observation.name
        if scheduler.current_observation
        else None,
    }
    return serialize_all_objects({"result": status})


@app.get("/has_valid_observations")
def has_valid_observations(request: Request):
    scheduler = get_scheduler(request)
    return {"result": scheduler.has_valid_observations}


@app.get("/get_observation")
def get_observation(request: Request, time: str | None = None):
    scheduler = get_scheduler(request)

    t = Time(time) if time else None
    obs = scheduler.get_observation(time=t)

    if obs:
        return {"result": obs.name}
    return {"result": None}


@app.post("/clear_available_observations")
def clear_available_observations(request: Request):
    scheduler = get_scheduler(request)
    scheduler.clear_available_observations()
    return {"result": True}


@app.post("/reset_observed_list")
def reset_observed_list(request: Request):
    scheduler = get_scheduler(request)
    scheduler.reset_observed_list()
    return {"result": True}


class ObservationConfig(BaseModel):
    observation_config: dict[str, Any]


@app.post("/add_observation")
def add_observation(request: Request, config: ObservationConfig):
    scheduler = get_scheduler(request)
    try:
        scheduler.add_observation(config.observation_config)
        return {"result": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/remove_observation")
def remove_observation(request: Request, field_name: str):
    scheduler = get_scheduler(request)
    scheduler.remove_observation(field_name)
    return {"result": True}
