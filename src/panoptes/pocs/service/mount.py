import threading
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional, List

from fastapi import FastAPI

from panoptes.utils.serializers import to_json
from panoptes.pocs.mount.mount import AbstractMount
from panoptes.pocs.mount import create_mount_from_config
from panoptes.pocs.mount import create_mount_simulator
from pydantic import BaseModel

app = FastAPI()


@dataclass
class MountService:
    mount: Optional[AbstractMount] = None

    def do_setup(self):
        self.mount = create_mount_simulator()

        return self.mount is not None


mount_service: MountService = MountService()


class RequestedCommand(BaseModel):
    command: str
    params: Optional[dict] = {}


@app.get('/')
def root():
    return 'Mount Service'


@app.get('/status')
def mount_status():
    try:
        return f'Status: {mount_service.mount.status}'
    except Exception:
        return 'Needs input'


@app.post('/config')
def do_config(command: RequestedCommand):
    try:
        cmd = getattr(mount_service, f'do_{command.command}')
        return cmd(**command.params)
    except Exception:
        return 'Does not compute.'
