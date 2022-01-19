from enum import auto
from typing import Union, Optional

from fastapi import FastAPI
from fastapi_utils.enums import StrEnum
from fastapi_utils.tasks import repeat_every
from panoptes.utils.config.client import get_config
from pydantic import BaseModel

from panoptes.pocs.sensor.power import PowerBoard


class RelayAction(StrEnum):
    turn_on = auto()
    turn_off = auto()


class RelayCommand(BaseModel):
    relay: Union[str, int]
    command: RelayAction


app = FastAPI()
power_board: PowerBoard
read_interval = get_config('environment.power.read_interval', default=60)


@app.on_event('startup')
async def startup():
    global power_board
    power_board = PowerBoard(**get_config('environment.power', {}))


@app.on_event('startup')
@repeat_every(seconds=60, wait_first=True)
def record_readings():
    """Record the current readings in the db."""
    global power_board
    return power_board.record(collection_name='power')


@app.get('/')
async def status():
    """Returns the power board status."""
    global power_board
    return power_board.status


@app.post('/readings')
async def readings(relay: Optional[str] = None):
    """Return the current readings as a dict."""
    global power_board
    readings_df = power_board.to_dataframe()
    print(f'Checking for {relay=}')
    if relay in readings_df:
        readings_df = readings_df[relay].as_frame()
    return readings_df.to_dict()


@app.post('/control')
def control_relay(relay_command: RelayCommand):
    """Control a relay via a POST request."""
    do_command(relay_command)
    return status()


@app.get('/relay/{relay}/control/{command}')
def control_relay_url(relay: Union[int, str], command: str = 'turn_on'):
    """Control a relay via a GET request"""
    do_command(RelayCommand(relay=relay, command=command))
    return status()


def do_command(relay_command: RelayCommand):
    """Control a relay.

    This function performs the actual relay control and is used by both request
    types.
    """
    global power_board
    relay_id = relay_command.relay
    try:
        relay = power_board.relay_labels[relay_id]
    except KeyError:
        relay = power_board.relays[relay_id]

    command_func = getattr(relay, relay_command.command)
    # Perform function.
    command_func()
    return relay_command
