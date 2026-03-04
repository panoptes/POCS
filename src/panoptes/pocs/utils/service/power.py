"""FastAPI service exposing power board status, readings, and control endpoints.

This module initializes a PowerBoard instance during application lifespan and
periodically records telemetry to the database. It exposes simple REST endpoints
for querying current status/readings and for toggling relays via POST/GET.
"""

import time
from contextlib import asynccontextmanager
from enum import StrEnum
from threading import Thread
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel

from panoptes.utils.config.client import get_config

from panoptes.pocs.sensor.power import PowerBoard


class RelayAction(StrEnum):
    """Enumeration of supported relay actions."""

    turn_on = "turn_on"
    turn_off = "turn_off"


class RelayCommand(BaseModel):
    """Command payload for controlling a relay.

    Attributes:
        relay (str | int): Relay label or index.
        command (RelayAction): Action to perform on the relay.
    """

    relay: str | int
    command: RelayAction


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
    app.state.power_board = power_board
    app.state.conf = conf

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


def get_power_board(request: Request) -> PowerBoard:
    """Dependency that retrieves the PowerBoard from application state.

    Args:
        request (Request): The incoming FastAPI request.

    Returns:
        PowerBoard: The active PowerBoard instance.
    """
    return request.app.state.power_board


PowerBoardDep = Annotated[PowerBoard, Depends(get_power_board)]


@app.get("/")
async def root(power_board: PowerBoardDep):
    """Returns the power board status."""
    return power_board.status


@app.get("/readings")
async def readings(power_board: PowerBoardDep):
    """Return the current readings as a dict."""
    return power_board.to_dataframe().to_dict()


@app.post("/control")
def control_relay(relay_command: RelayCommand, power_board: PowerBoardDep):
    """Control a relay via a POST request.

    Args:
        relay_command (RelayCommand): The relay identifier and action to perform.
        power_board (PowerBoardDep): The active PowerBoard instance.

    Returns:
        RelayCommand: Echo of the command that was executed upon success.
    """
    return do_command(relay_command, power_board)


@app.get("/relay/{relay}/control/{command}")
def control_relay_url(relay: int | str, power_board: PowerBoardDep, command: str = "turn_on"):
    """Control a relay via a GET request.

    Args:
        relay (int | str): The relay index or label to control.
        power_board (PowerBoardDep): The active PowerBoard instance.
        command (str): The action to perform, e.g. "turn_on" or "turn_off".

    Returns:
        RelayCommand: Echo of the command that was executed upon success.

    Raises:
        HTTPException: 422 if the command string is not a valid RelayAction.
    """
    try:
        action = RelayAction(command)
    except ValueError:
        valid = [a.value for a in RelayAction]
        raise HTTPException(status_code=422, detail=f"Invalid command '{command}'. Must be one of: {valid}")
    return do_command(RelayCommand(relay=relay, command=action), power_board)


def do_command(relay_command: RelayCommand, power_board: PowerBoard):
    """Control a relay.

    This function performs the actual relay control and is used by both request
    types.

    Args:
        relay_command (RelayCommand): The relay identifier and action to execute.
        power_board (PowerBoard): The active PowerBoard instance.

    Returns:
        RelayCommand: Echo of the command that was executed.
    """
    relay_id = relay_command.relay
    try:
        relay = power_board.relay_labels[relay_id]
    except KeyError:
        relay = power_board.relays[int(relay_id)]

    command_func = getattr(relay, relay_command.command)
    # Perform function.
    command_func()
    return relay_command
