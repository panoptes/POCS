import time
from typing import Union

from fastapi import FastAPI
from fastapi_utils.tasks import repeat_every
from panoptes.pocs.sensor.power import PowerBoard
from panoptes.utils.config.client import get_config
from pydantic import BaseModel


class RelayCommand(BaseModel):
    relay: Union[str, int]
    command: str


app = FastAPI()
power_board: PowerBoard


@app.on_event('startup')
async def startup():
    global power_board
    power_board = PowerBoard(**get_config('environment.power', {}))


@app.get('/')
@repeat_every(seconds=60)
async def root():
    return power_board.status


@app.get('/readings')
async def readings():
    return power_board.to_dataframe().to_dict()


@app.post('/control')
def control_relay(relay_command: RelayCommand):
    return do_command(relay_command)


@app.get('/relays/{relay}/control/{command}')
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
