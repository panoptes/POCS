import time
from enum import Enum
from typing import Union

from fastapi import FastAPI
from pydantic import BaseModel
from panoptes.utils.config.client import get_config
from panoptes.pocs.sensor.power import PowerBoard


class RelayAction(str, Enum):
    turn_on = 'turn_on'
    turn_off = 'turn_off'


class RelayCommand(BaseModel):
    relay: Union[str, int]
    command: RelayAction


app = FastAPI()
power_board: PowerBoard


@app.on_event('startup')
async def startup():
    global power_board
    power_board = PowerBoard(**get_config('environment.power', {}))


@app.get('/')
async def root():
    """Returns the power board status."""
    global power_board
    return power_board.status


@app.get('/readings')
async def readings():
    """Return the current readings as a dict."""
    global power_board
    return power_board.to_dataframe().to_dict()


@app.get('/record')
def record_readings():
    """Record the current readings in the db."""
    global power_board
    return power_board.record()


@app.post('/control')
def control_relay(relay_command: RelayCommand):
    """Control a relay via a POST request."""
    return do_command(relay_command)


@app.get('/relay/{relay}/control/{command}')
def control_relay_url(relay: Union[int, str], command: str = 'turn_on'):
    """Control a relay via a GET request"""
    return do_command(RelayCommand(relay=relay, command=command))


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
