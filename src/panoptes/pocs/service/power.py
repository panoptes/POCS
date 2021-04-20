import time
from typing import Union

from fastapi import FastAPI

from panoptes.utils.config.client import get_config
from panoptes.pocs.sensor.power import PowerBoard

app = FastAPI()

power_board = PowerBoard(**get_config('environment.power'))


@app.get('/')
async def root():
    return power_board.status


@app.get('/readings')
async def readings():
    return power_board.to_dataframe().to_dict()


@app.get('/relays/{relay_index}/control/{action}')
def control_relay(relay_index: Union[int, str], action: str = 'turn_on'):
    try:
        relay = power_board.relay_labels[relay_index]
    except KeyError:
        relay = power_board.relays[relay_index]

    action_func = getattr(relay, action)
    # Perform function.
    action_func()
    time.sleep(1)  # Give it time to toggle before returning status
    return power_board.status
