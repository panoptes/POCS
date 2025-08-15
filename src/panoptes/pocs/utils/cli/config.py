import subprocess
from typing import Optional, Dict

import typer
from astropy import units as u
from pydantic import BaseModel
from rich import print
from rich import prompt
from rich.console import Console

from panoptes.pocs.utils.logger import get_logger
from panoptes.utils.config.client import get_config, set_config, server_is_running


class HostInfo(BaseModel):
    """Metadata for the Config Server"""

    host: str = "127.0.0.1"
    port: int = 6563
    verbose: bool = False

    @property
    def url(self):
        return f"{self.host}:{self.port}"


app = typer.Typer()
host_info: Dict[str, Optional[HostInfo]] = {"config_server": None}
logger = get_logger(stderr_log_level="ERROR")


def server_running():
    """Check if the config server is running"""
    # NOTE: A bug in server_is_running means we cannot specify the port.
    is_running = server_is_running()
    if is_running is None or is_running is False:
        print("[red]The config server is not running. Please start it first.[/red]")

    return is_running


@app.callback()
def main(context: typer.Context):
    context.params.update(context.parent.params)
    verbose = context.params["verbose"]
    host_info["config_server"] = HostInfo(
        host=context.params["config_host"], port=context.params["config_port"], verbose=verbose
    )
    if verbose:
        print(f"Command options from power: {context.params!r}")


@app.command()
def status():
    server_running()


@app.command(name="get")
def get_value(
    key: Optional[str] = typer.Argument(
        None,
        help="The key of the config item to get. "
        "Can be specified in dotted-key notation "
        "e.g. `directories.images`",
    ),
    parse: bool = typer.Option(True, help="Parse the item."),
):
    """Get an item from the config"""
    if server_running():
        metadata = host_info["config_server"]
        item = get_config(key, parse=parse, host=metadata.host, port=metadata.port)
        print(item)


@app.command(name="set")
def set_value(
    key: str = typer.Argument(
        ...,
        help="The key, in dotted-notation, of the config item to get."
        "A blank string (the default) will return the entire config.",
    ),
    value: str = typer.Argument(..., help="The new value."),
):
    """Get an item from the config"""
    if server_running():
        metadata = host_info["config_server"]
        if value.startswith(r"\-"):
            value = value[1:]
        try:
            value = int(value)
        except ValueError:
            try:
                value = float(value)
            except ValueError:
                print(f"{value=} is not a number.")
        print(f"{type(value)=} {value=}")
        item = set_config(key, value, host=metadata.host, port=metadata.port)
        print(item)


@app.command()
def setup():
    """Do initial setup of the config server"""
    # Clear the screen.
    console = Console()
    console.clear()
    if not server_running():
        raise typer.Exit()

    print(f"Setting up configuration for your PANOPTES unit.")
    # Make sure they want to proceed.
    proceed = prompt.Confirm.ask(
        "This will overwrite any existing configuration. Proceed?", default=False
    )
    if not proceed:
        print("Exiting.")
        return

    # Set the base directory.
    base_dir = prompt.Prompt.ask("Enter the base directory for POCS", default="/home/panoptes/POCS")
    set_config("directories.base", base_dir)

    # Get the user-friendly name for the unit.
    unit_name = prompt.Prompt.ask(
        "Enter the user-friendly name for this unit", default=get_config("name")
    )
    set_config("name", unit_name)

    # Get the pan_id for the unit.
    pan_id = prompt.Prompt.ask(
        "Enter the PANOPTES ID for this unit. If you don't have one yet just use the default:",
        default=get_config("pan_id"),
    )
    set_config("pan_id", pan_id)

    # Latitude
    latitude = prompt.Prompt.ask(
        'Enter the latitude for this unit, e.g. "19.5 deg":',
        default=str(get_config("location.latitude")),
    )
    set_config("location.latitude", str(u.Unit(latitude)))
    # Longitude
    longitude = prompt.Prompt.ask(
        'Enter the longitude for this unit, e.g. "-154.12 deg":',
        default=str(get_config("location.longitude")),
    )
    set_config("location.longitude", str(u.Unit(longitude)))
    # Elevation
    elevation = prompt.Prompt.ask(
        "Enter the elevation for this unit. "
        'Use " ft" or " m" for units, e.g. "3400 m" or "12000 ft":',
        default=str(get_config("location.elevation")),
    )
    if " ft" in elevation:
        elevation = (elevation.replace(" ft", "") * u.imperial.foot).to(u.meter)
    elif elevation.endswith("m"):
        elevation = str(u.Unit(elevation))
    set_config("location.elevation", elevation)

    # Default timezone to UTC but try to probe OS.
    timezone = "UTC"
    try:
        timezone = subprocess.check_output("cat /etc/timezone", shell=True).decode().strip()
    except subprocess.CalledProcessError as e:
        pass

    timezone = prompt.Prompt.ask("Enter the timezone for this unit", default=timezone)
    set_config("location.timezone", timezone)

    # Get GMT offset and then confirm if correct.
    gmt_offset = subprocess.check_output("date +%z", shell=True).decode().strip()
    # Convert GMT offset to minutes.
    gmt_offset = int(gmt_offset[:3]) * 60 + int(gmt_offset[-2:])
    gmt_offset = prompt.Prompt.ask(
        "Enter the GMT offset for this unit in minutes, "
        "e.g. 60 for 1 hour ahead, -120 for 2 hours behind:",
        default=str(gmt_offset),
    )
    set_config("location.gmt_offset", int(gmt_offset))


@app.command()
def restart():
    """Restart the config server process via supervisorctl"""
    cmd = f"supervisorctl restart pocs-config-server"
    print(f"Running: {cmd}")
    subprocess.run(cmd, shell=True)


if __name__ == "__main__":
    app()
