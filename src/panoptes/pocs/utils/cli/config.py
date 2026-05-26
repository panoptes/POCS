"""Typer CLI helpers for interacting with the PANOPTES config file."""

import os
import subprocess

import typer
from astropy import units as u
from rich import print, prompt
from rich.console import Console

from panoptes.utils.config.helpers import save_config

from panoptes.pocs.config import store as config_store
from panoptes.pocs.utils.logger import get_logger

app = typer.Typer(no_args_is_help=True)
logger = get_logger(stderr_log_level="ERROR")


@app.command()
def status():
    """Print config availability status."""
    config_store.get_config()
    print("[green]Config is ready.[/green]")


@app.command(name="get")
def get_value(
    key: str | None = typer.Argument(
        None,
        help="The key of the config item to get. "
        "Can be specified in dotted-key notation "
        "e.g. `directories.images`",
    ),
    parse: bool = typer.Option(True, help="Parse the item."),
):
    """Get an item from the config."""
    del parse
    item = config_store.get_config(key)
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
    """Set an item in the config."""
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
    item = config_store.set_config(key, value)
    print(item)


@app.command()
def setup():
    """Do initial setup of the config file."""
    console = Console()
    console.clear()

    print("Setting up configuration for your PANOPTES unit.")
    proceed = prompt.Confirm.ask("This will overwrite any existing configuration. Proceed?", default=False)
    if not proceed:
        print("Exiting.")
        return

    base_dir = prompt.Prompt.ask(
        "Enter the base directory for POCS", default=f"{os.path.expanduser('~')}/POCS"
    )
    config_store.set_config("directories.base", base_dir)

    unit_name = prompt.Prompt.ask(
        "Enter the user-friendly name for this unit", default=config_store.get_config("name")
    )
    config_store.set_config("name", unit_name)

    pan_id = prompt.Prompt.ask(
        "Enter the PANOPTES ID for this unit. If you don't have one yet just use the default:",
        default=config_store.get_config("pan_id"),
    )
    config_store.set_config("pan_id", pan_id)

    latitude = prompt.Prompt.ask(
        'Enter the latitude for this unit, e.g. "19.5 deg":',
        default=str(config_store.get_config("location.latitude")),
    )
    config_store.set_config("location.latitude", str(u.Unit(latitude)))

    longitude = prompt.Prompt.ask(
        'Enter the longitude for this unit, e.g. "-154.12 deg":',
        default=str(config_store.get_config("location.longitude")),
    )
    config_store.set_config("location.longitude", str(u.Unit(longitude)))

    elevation = prompt.Prompt.ask(
        'Enter the elevation for this unit. Use " ft" or " m" for units, e.g. "3400 m" or "12000 ft":',
        default=str(config_store.get_config("location.elevation")),
    )
    if " ft" in elevation:
        elevation = (float(elevation.replace(" ft", "")) * u.imperial.foot).to(u.meter)
    elif elevation.endswith("m"):
        elevation = str(u.Unit(elevation))
    config_store.set_config("location.elevation", elevation)

    timezone = "UTC"
    try:
        timezone = subprocess.check_output(["cat", "/etc/timezone"], text=True).strip()
    except subprocess.CalledProcessError:
        pass

    timezone = prompt.Prompt.ask("Enter the timezone for this unit", default=timezone)
    config_store.set_config("location.timezone", timezone)

    gmt_offset = subprocess.check_output(["date", "+%z"], text=True).strip()
    gmt_offset = int(gmt_offset[:3]) * 60 + int(gmt_offset[-2:])
    gmt_offset = prompt.Prompt.ask(
        "Enter the GMT offset for this unit in minutes, e.g. 60 for 1 hour ahead, -120 for 2 hours behind:",
        default=str(gmt_offset),
    )
    config_store.set_config("location.gmt_offset", int(gmt_offset))
    save_config(config=config_store.get_config())
    print("[green]Config saved.[/green]")


if __name__ == "__main__":
    app()
