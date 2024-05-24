from contextlib import asynccontextmanager
from enum import auto
from typing import Union

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


app_objects = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Context manager for the lifespan of the app."""
    conf: dict = get_config('environment.power', {})
    power_board = PowerBoard(**conf)
    power_board.logger.info(f'Power board setup: {power_board}')
    app_objects['power_board'] = power_board
    app_objects['conf'] = conf
    yield
    power_board.logger.info('Shutting down power board')


app = FastAPI(lifespan=lifespan)


@repeat_every(seconds=60, wait_first=True)
def record_readings():
    """Record the current readings in the db."""
    power_board = app_objects['power_board']
    return power_board.record(collection_name='power')


@app.get('/')
async def root():
    """Returns the power board status."""
    power_board = app_objects['power_board']
    return power_board.status


@app.get('/readings')
async def readings():
    """Return the current readings as a dict."""
    power_board = app_objects['power_board']
    return power_board.to_dataframe().to_dict()


@app.post('/control')
def control_relay(relay_command: RelayCommand):
    """Control a relay via a POST request."""
    return do_command(relay_command)


@app.get('/relay/{relay}/control/{command}')
def control_relay_url(relay: Union[int, str], command: str = 'turn_on'):
    """Control a relay via a GET request"""
    return do_command(RelayCommand(relay=relay, command=RelayAction(command)))


def do_command(relay_command: RelayCommand):
    """Control a relay.

    This function performs the actual relay control and is used by both request
    types.
    """
    power_board = app_objects['power_board']
    relay_id = relay_command.relay
    try:
        relay = power_board.relay_labels[relay_id]
    except KeyError:
        relay = power_board.relays[int(relay_id)]

    command_func = getattr(relay, relay_command.command)
    # Perform function.
    command_func()
    return relay_command
