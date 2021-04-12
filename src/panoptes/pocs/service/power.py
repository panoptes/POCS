from enum import Enum, auto
from typing import Optional, Mapping

from fastapi import FastAPI
from panoptes.utils.serializers import to_json
from pydantic import BaseModel

from panoptes.pocs.mount import create_mount_simulator

app = FastAPI()


class ExposedMethods(Enum):
    status = auto()
    unpark = auto()
    park = auto()


class DeviceCommand(BaseModel):
    command: str
    params: Optional[Mapping]



device = None


@app.get('/setup')
def setup():
    global device
    device = create_mount_simulator()

    return f'Created: {device.status}'


@app.get('/')
def root():
    return f'Needs input: {device}'


@app.get('/status')
def status():
    return f'Status: {device.status}'


@app.post('/command')
def do_command(command: DeviceCommand):
    cmd = getattr(device, command.command)
    params = command.params or dict()
    result = cmd(**params)

    return result
