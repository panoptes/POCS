import os
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi_utils.tasks import repeat_every
from panoptes.utils.config.client import get_config
from serial.tools.list_ports import comports as get_comports

from panoptes.pocs.sensor.weather import WeatherStation

app_objects = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Context manager for the lifespan of the app.

    This will connect to the weather station and record
    readings at a regular interval.
    """
    conf = get_config('environment.weather', {})
    app_objects['conf'] = conf

    # Get list of possible ports for auto-detect or use the configured port.
    if conf.get('auto_detect', False) is True:
        ports = [p.device for p in get_comports()]
    else:
        ports = [conf['serial_port']]

    # Check the ioptron symlink and skip that port if it exists.
    ioptron_port = None
    with suppress(FileNotFoundError):
        ioptron_port = os.readlink('/dev/ioptron')

    # Try to connect to the weather station.
    for port in ports:
        if 'ttyUSB' not in port:
            continue

        if port == ioptron_port:
            continue

        conf['serial_port'] = port
        try:
            weather_station = WeatherStation(**conf)
            weather_station.logger.info(f'Weather station setup: {weather_station}')
            app_objects['weather_station'] = weather_station
            break
        except Exception as e:
            print(f'Could not connect to weather station on {port}: {e}')
    else:
        raise RuntimeError('Could not connect to weather station.')

    yield
    print('Shutting down weather station')


app = FastAPI(lifespan=lifespan)


@app.on_event('startup')
@repeat_every(seconds=60, wait_first=True)
def record_readings():
    """Record the current readings in the db."""
    weather_station = app_objects['weather_station']
    reading = weather_station.record()
    weather_station.logger.debug(f'Recorded weather reading: {reading}')
    return reading


@app.get('/status')
async def status():
    """Returns the power board status."""
    return app_objects['weather_station'].status


@app.get('/config')
async def get_ws_config():
    """Returns the power board status."""
    return app_objects['weather_station']
