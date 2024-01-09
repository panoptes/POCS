from fastapi import FastAPI
from fastapi_utils.tasks import repeat_every
from panoptes.utils.config.client import get_config
from serial.tools.list_ports import comports as get_comports

from panoptes.pocs.sensor.weather import WeatherStation

app = FastAPI()
weather_station: WeatherStation


@app.on_event('startup')
async def startup():
    global weather_station

    conf = get_config('environment.weather', {})

    if conf.get('auto_detect', False) is True:
        ports = [p.device for p in get_comports()]
    else:
        ports = [conf['port']]

    # Probe for the weather station serial port.
    for port in ports:
        if 'ioptron' in port:
            continue

        conf['port'] = port
        try:
            weather_station = WeatherStation(**conf)
            break
        except Exception as e:
            print(f'Could not connect to weather station on {port}: {e}')
    else:
        raise RuntimeError('Could not connect to weather station.')


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
