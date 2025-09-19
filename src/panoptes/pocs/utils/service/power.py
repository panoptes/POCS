"""FastAPI service exposing power board status, readings, and control endpoints.

This module initializes a PowerBoard instance during application lifespan and
periodically records telemetry to the database. It exposes simple REST endpoints
for querying current status/readings and for toggling relays via POST/GET.
"""
import time
from contextlib import asynccontextmanager
from enum import auto
from threading import Thread
from typing import Union

from fastapi import FastAPI
from fastapi_utils.enums import StrEnum
from panoptes.utils.config.client import get_config
from pydantic import BaseModel

from panoptes.pocs.sensor.power import PowerBoard


class RelayAction(StrEnum):
    """Enumeration of supported relay actions."""

    turn_on = auto()
    turn_off = auto()


class RelayCommand(BaseModel):
    """Command payload for controlling a relay.

    Attributes:
        relay (str | int): Relay label or index.
        command (RelayAction): Action to perform on the relay.
    """

    relay: Union[str, int]
    command: RelayAction


app_objects = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Context manager for the FastAPI application's lifespan.

    This will connect to the power board and start a background thread that
    periodically records readings at a configured interval.

    Args:
        app (FastAPI): The FastAPI application instance.

    Yields:
        None: Control to FastAPI while the app is running.
    """
    conf: dict = get_config("environment.power", {})
    power_board = PowerBoard(**conf)
    power_board.logger.info(f"Power board setup: {power_board}")
    app_objects["power_board"] = power_board
    app_objects["conf"] = conf

    # Set up a thread to record the readings at an interval.
    def record_readings():
        """Record the current readings in the db."""
        record_interval = conf.get("record_interval", 60)
        power_board.logger.info(f"Setting up power recording {record_interval=}")
        while True:
            time.sleep(record_interval)
            try:
                power_board.record(collection_name="power")
            except Exception as e:
                power_board.logger.warning(f"Could not get power record: {e}")

    # Create a thread to record the readings at an interval.
    power_thread = Thread(target=record_readings)
    power_thread.daemon = True
    power_thread.start()

    yield
    power_board.logger.info("Shutting down power board, please wait.")
    power_thread.join()


app = FastAPI(lifespan=lifespan)


@app.get("/")
async def root():
    """Returns the power board status."""
    power_board = app_objects["power_board"]
    return power_board.status


@app.get("/readings")
async def readings():
    """Return the current readings as a dict."""
    power_board = app_objects["power_board"]
    return power_board.to_dataframe().to_dict()


@app.post("/control")
def control_relay(relay_command: RelayCommand):
    """Control a relay via a POST request.

    Args:
        relay_command (RelayCommand): The relay identifier and action to perform.

    Returns:
        RelayCommand: Echo of the command that was executed upon success.
    """
    return do_command(relay_command)


@app.get("/relay/{relay}/control/{command}")
def control_relay_url(relay: Union[int, str], command: str = "turn_on"):
    """Control a relay via a GET request.

    Args:
        relay (int | str): The relay index or label to control.
        command (str): The action to perform, e.g. "turn_on" or "turn_off".

    Returns:
        RelayCommand: Echo of the command that was executed upon success.
    """
    return do_command(RelayCommand(relay=relay, command=RelayAction(command)))


def do_command(relay_command: RelayCommand):
    """Control a relay.

    This function performs the actual relay control and is used by both request
    types.

    Args:
        relay_command (RelayCommand): The relay identifier and action to execute.

    Returns:
        RelayCommand: Echo of the command that was executed.
    """
    power_board = app_objects["power_board"]
    relay_id = relay_command.relay
    try:
        relay = power_board.relay_labels[relay_id]
    except KeyError:
        relay = power_board.relays[int(relay_id)]

    command_func = getattr(relay, relay_command.command)
    # Perform function.
    command_func()
    return relay_command
