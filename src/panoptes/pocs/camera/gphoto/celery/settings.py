import typing
from enum import IntEnum
from typing import Dict, Optional

import pigpio
from pydantic import BaseSettings, BaseModel, Field

from worker import gpio


class State(IntEnum):
    LOW = 0
    HIGH = 1


class Settings(BaseSettings):
    camera_name: str
    camera_port: str
    camera_pin: int
    broker_url: str = 'amqp://guest:guest@localhost:5672//'
    result_backend: str = 'rpc://'

    class Config:
        env_prefix = 'pocs_'


class Camera(BaseModel):
    """A camera with a shutter release connected to a gpio pin."""
    name: str
    port: str
    pin: int
    is_tethered: bool = False

    def setup_pin(self):
        """Sets the mode for the GPIO pin."""
        # Get GPIO pin and set OUTPUT mode.
        print(f'Setting {self.pin=} as OUTPUT for {self.name}')
        gpio.set_mode(self.pin, pigpio.OUTPUT)


class AppSettings(BaseModel):
    celery: Dict = Field(default_factory=dict)
    camera: Camera
    process: Optional[typing.Any] = None
