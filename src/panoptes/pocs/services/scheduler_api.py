from contextlib import asynccontextmanager
from typing import Any

from astropy.time import Time
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

from panoptes.utils.serializers import serialize_all_objects
from panoptes.pocs.scheduler import create_scheduler_from_config
from panoptes.pocs.utils.logger import get_logger

logger = get_logger()


import asyncio

@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan context manager that manages the scheduler instance."""
    app.state.scheduler = None
    
    # Attempt to initialize hardware during startup.
    # We retry a few times in case the config server is still starting up.
    for i in range(10):
        try:
            logger.info(f"Startup attempt {i+1}/10 to create scheduler.")
            app.state.scheduler = create_scheduler_from_config(client_mode=False)
            if app.state.scheduler:
                logger.success("Scheduler created and initialized with fields.")
                break
        except Exception as e:
            logger.warning(f"Scheduler creation attempt {i+1} failed: {e!r}")
            await asyncio.sleep(2)
    yield


app = FastAPI(lifespan=lifespan)


def get_scheduler(request: Request):
    """Retrieve the scheduler instance from the FastAPI application state."""
    scheduler = getattr(request.app.state, "scheduler", None)
    
    # If scheduler not initialized, try once more lazily.
    if scheduler is None:
        logger.info("Scheduler not initialized, attempting lazy creation.")
        try:
            scheduler = create_scheduler_from_config(client_mode=False)
            if scheduler:
                request.app.state.scheduler = scheduler
        except Exception as e:
            logger.error(f"Lazy scheduler creation failed: {e!r}")

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
