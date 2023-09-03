from fastapi import FastAPI
from fastapi_utils.tasks import repeat_every
from panoptes.utils.config.client import get_config

from panoptes.pocs.sensor.weather import WeatherStation

app = FastAPI()
weather_station: WeatherStation
read_interval = get_config('environment.weather.read_interval', default=60)


@app.on_event('startup')
async def startup():
    global weather_station
    weather_station = WeatherStation(**get_config('environment.weather', {}))


@app.on_event('startup')
@repeat_every(seconds=60, wait_first=True)
def record_readings():
    """Record the current readings in the db."""
    global weather_station
    return weather_station.record()


@app.get('/')
async def root():
    """Returns the power board status."""
    global weather_station
    return weather_station.status
