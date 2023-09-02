from enum import auto
from typing import Union

from fastapi import FastAPI
from fastapi_utils.enums import StrEnum
from fastapi_utils.tasks import repeat_every
from panoptes.utils.config.client import get_config
from pydantic import BaseModel

from aag.weather import CloudSensor

from panoptes.pocs.base import PanBase

app = FastAPI()
weather_station: CloudSensor
read_interval = get_config('environment.power.read_interval', default=60)


@app.on_event('startup')
async def startup():
    global weather_station
    weather_station = CloudSensor(**get_config('environment.weather', {}))


@app.on_event('startup')
@repeat_every(seconds=60, wait_first=True)
def record_readings():
    """Record the current readings in the db."""
    global weather_station
    return weather_station.record(collection_name='power')


@app.get('/')
async def root():
    """Returns the power board status."""
    global weather_station
    return weather_station.status


@app.get('/readings')
async def readings():
    """Return the current readings as a dict."""
    global weather_station
    return weather_station.to_dataframe().to_dict()
