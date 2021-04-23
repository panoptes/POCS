import time
from enum import Enum
from typing import Union

from fastapi import FastAPI
from panoptes.pocs.sensor.power import PowerBoard
from panoptes.utils.config.client import get_config
from pydantic import BaseModel


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
    return power_board.status


@app.get('/readings')
async def readings():
    return power_board.to_dataframe().to_dict()


@app.post('/control')
def control_relay(relay_command: RelayCommand):
    return do_command(relay_command)


@app.get('/relay/{relay}/control/{command}')
def control_relay_url(relay: Union[int, str], command: str = 'turn_on'):
    return do_command(RelayCommand(relay=relay, command=command))


def do_command(relay_command: RelayCommand):
    relay_id = relay_command.relay
    try:
        relay = power_board.relay_labels[relay_id]
    except KeyError:
        relay = power_board.relays[relay_id]

    command_func = getattr(relay, relay_command.command)
    # Perform function.
    command_func()
    time.sleep(1)  # Give it time to toggle before returning status
    return power_board.status
