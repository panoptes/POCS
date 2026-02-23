"""Typer CLI for interacting with the power monitoring/control service.

Provides commands to query relay status and readings, and to toggle relays via
HTTP calls to the FastAPI service implemented in panoptes.pocs.utils.service.power.
"""

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import numpy as np
import requests
import typer
from rich import print
from sparklines import sparklines

from panoptes.pocs.utils.service.power import RelayCommand


@dataclass
class HostInfo:
    """Simple host/port holder for the power service.

    Attributes:
        host (str): Hostname or IP address of the power service.
        port (str): TCP port for the service (string for simple concatenation).
    """

    host: str = "localhost"
    port: str = "6564"

    @property
    def url(self):
        """Assemble the base URL for the power service.

        Returns:
            str: The base http URL including host and port.
        """
        return f"http://{self.host}:{self.port}"


app = typer.Typer(no_args_is_help=True)


@app.callback()
def common(
    context: typer.Context,
    host: str = typer.Option("localhost", help="Power monitor host address."),
    port: str = typer.Option("6564", help="Power monitor port."),
):
    """Shared options setup for all power CLI commands.

    Args:
        context: Typer context used to share HostInfo across commands.
        host: Power service host address.
        port: Power service TCP port.

    Returns:
        None
    """
    context.obj = HostInfo(host=host, port=port)


@app.command()
def status(context: typer.Context):
    """Get and display the status of the power monitor relays.

    Args:
        context: Typer context containing HostInfo with the server URL.

    Returns:
        None
    """
    url = context.obj.url
    try:
        res = requests.get(url)
        if res.ok:
            relays = res.json()
            for relay_index, relay_info in relays.items():
                try:
                    relay_label = f"{relay_info['label']:.<20s}"
                    print(
                        f"[{relay_index:.<12s}] "
                        f"{relay_label} [{'green' if relay_info['state'] == 'ON' else 'red'}]"
                        f"{relay_info['state']}[/]"
                    )
                except (KeyError, TypeError):
                    print(f"[{relay_index.upper():.<12s}] {str(relay_info):.>23s}")
        else:
            print(f"[red]{res.content.decode()}[/red]")
    except requests.exceptions.ConnectionError:
        print(f"[red]Cannot connect to {url}[/red]")


@app.command()
def readings(context: typer.Context):
    """Fetch and display recent readings for each relay.

    Args:
        context: Typer context containing HostInfo with base URL.

    Returns:
        None
    """
    url = context.obj.url + "/readings"
    try:
        res = requests.get(url)
        if res.ok:
            relays = res.json()
            for relay_label, relay_readings in relays.items():
                relay_text = f"[cyan]{relay_label:.<20s}[/cyan]"
                relay_readings = [int(x) if int(x) >= 0 else 0 for x in relay_readings.values()]
                for val in sparklines(relay_readings):
                    print(f"{relay_text} {val} [{np.array(relay_readings).mean():.0f}]")
        else:
            print(f"[red]{res.content.decode()}[/red]")
    except requests.exceptions.ConnectionError:
        print(f"[red]Cannot connect to {url}[/red]")


@app.command()
def on(
    context: typer.Context,
    relay: str = typer.Argument(..., help="The label or index of the relay to turn on."),
):
    """Turn a relay on by label or index.

    Args:
        context: Typer context carrying HostInfo state.
        relay: Relay label or index to control.

    Returns:
        None
    """
    control(context, relay=relay, command="turn_on")


@app.command()
def off(
    context: typer.Context,
    relay: str = typer.Argument(..., help="The label or index of the relay to turn off."),
):
    """Turn a relay off by label or index.

    Args:
        context: Typer context carrying HostInfo state.
        relay: Relay label or index to control.

    Returns:
        None
    """
    control(context, relay=relay, command="turn_off")


@app.command()
def control(
    context: typer.Context,
    relay: str = typer.Option(..., help="The label or index of the relay to control."),
    command: str = typer.Option(..., help='The control action to perform, either "turn_on" or "turn_off"'),
):
    """Control a relay by label or relay index.

    Args:
        context: Typer context with HostInfo state.
        relay: Relay label or index to control.
        command: Action to perform, either "turn_on" or "turn_off".

    Returns:
        None
    """
    url = context.obj.url + "/control"

    try:
        relay_command = RelayCommand(relay=relay, command=command)
        res = requests.post(url, data=relay_command.json())
        content = res.json() if res.ok else res.content.decode()
        print(content)
    except requests.exceptions.ConnectionError:
        print(f"[red]Cannot connect to {url}")


@app.command()
def restart():
    """Restart the power server process via supervisorctl"""
    cmd = "supervisorctl restart pocs-power-monitor"
    print(f"Running: {cmd}")
    subprocess.run(cmd, shell=True)


@app.command(name="setup")
def setup_power(
    confirm: Annotated[
        bool,
        typer.Option(
            ...,
            "--confirm",
            prompt="Are you sure you want to setup the power board?",
            help="Confirm power board setup.",
        ),
    ] = False,
    do_install: Annotated[
        bool,
        typer.Option(
            ...,
            "--install",
            prompt="Would you like to install the arduino script?",
            help="Install the arduino script.",
        ),
    ] = False,
    install_script: Path = typer.Option(
        "resources/arduino/install-power-board.sh", help="Path to the power monitor script."
    ),
):
    """Set up the power board port and labels; optionally install Arduino sketch.

    Args:
        confirm: Confirmation flag to proceed with setup.
        do_install: If True, run the Arduino install script before setup.
        install_script: Path to the Arduino install script.

    Returns:
        None
    """
    if not confirm:
        print("[red]Cancelled.[/red]")
        return typer.Abort()

    if do_install:
        if not install_script.exists():
            print(f"[red]Cannot find install script at {install_script}[/red]")
            return typer.Abort()
        # Change directory to the arduino script.
        os.chdir(install_script.parent)
        cmd = f"bash {install_script.name}"
        print(f"Running: {cmd}")
        try:
            subprocess.run(cmd, shell=True)
        except subprocess.CalledProcessError as e:
            print(f"[red]Error running install script: {e}[/red]")
        else:
            print("[green]Arduino script installed.[/green]")


if __name__ == "__main__":
    app()
