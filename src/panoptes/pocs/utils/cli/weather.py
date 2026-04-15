"""Typer CLI for interacting with the PANOPTES weather station service.

Provides commands to query status/config, restart the service, and set up
the weather station udev rules for persistent device naming.
"""

import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Annotated

import human_readable
import requests
import typer
from rich import print
from rich.console import Console
from rich.table import Table

from panoptes.utils.serial.device import get_serial_port_info


@dataclass
class HostInfo:
    """Class to store and manage weather station host information.

    This class stores the host and port information for a weather station
    and provides a property to generate the complete URL.
    """

    host: str = "localhost"
    port: str = "6566"

    @property
    def url(self):
        """Generate the complete URL for the weather station.

        Returns:
            str: The complete URL in the format 'http://{host}:{port}'
        """
        return f"http://{self.host}:{self.port}"


app = typer.Typer(no_args_is_help=True)


@app.callback()
def common(
    context: typer.Context,
    host: str = typer.Option("localhost", help="Weather station host address."),
    port: str = typer.Option("6566", help="Weather station port."),
):
    """Common callback for all commands in the weather CLI.

    This function sets up the context object with host information that will be
    available to all commands in the CLI application.

    Args:
        context: The Typer context object
        host: The hostname or IP address of the weather station
        port: The port number the weather station is listening on
    """
    context.obj = HostInfo(host=host, port=port)


@app.command(name="status", help="Get the status of the weather station.")
def status(context: typer.Context, page="status", show_raw_values: bool = False):
    """Get the status of the weather station.

    This command retrieves the latest weather data from the weather station and
    displays it in a formatted table on the command line. The table includes
    information about temperature, wind speed, cloud/wind/rain conditions, and
    their safety status.

    Args:
        context: The Typer context object containing the host information
        page: The API endpoint to query (defaults to 'status')
        show_raw_values: If True, prints the raw JSON data instead of a formatted table

    Returns:
        None: This function prints the weather data to the console
    """
    url = context.obj.url
    data = get_page(page, url)

    if isinstance(data, str) and data.startswith("No valid readings found"):
        print(f"[bold yellow]{data}[/bold yellow]")
        return

    if not show_raw_values:
        display_weather_table(data)


def display_weather_table(data: dict):
    """Display weather data in a formatted table.

    This function takes weather data in dictionary format and displays it in a
    nicely formatted table using the Rich library. The table includes information
    about temperatures, wind speed, and various safety conditions (cloud, wind, rain).
    The table is color-coded based on safety status (green for safe, red for unsafe).

    Args:
        data: A dictionary containing weather data with keys such as 'is_safe',
              'ambient_temp', 'sky_temp', 'wind_speed', 'cloud_condition',
              'wind_condition', 'rain_condition', 'timestamp', etc.

    Returns:
        None: This function prints the formatted table to the console

    Note:
        The table's title color is determined by the 'is_safe' value in the data.
        Individual rows for cloud, wind, and rain conditions are also color-coded
        based on their respective safety status.
    """
    # Create a Rich table
    is_safe = data["is_safe"]
    table = Table(title="Weather Station Status", style="bold green" if is_safe else "bold red")

    # Add columns for key and value
    table.add_column("Parameter", style="cyan")
    table.add_column("Value", style="green")
    table.add_column("Safety", style="green")

    # Show the sky and ambient temperature
    ambient_temp = data.get("ambient_temp")
    table.add_row("Ambient Temperature", f"{ambient_temp:>6.02f} C")

    sky_temp = data.get("sky_temp")
    table.add_row("Sky Temperature", f"{sky_temp:>6.02f} C")

    temp_diff = sky_temp - ambient_temp
    table.add_row("Sky - Ambient", f"{temp_diff:>6.02f} C")

    wind_speed = data.get("wind_speed")
    table.add_row("Wind Speed", f"{wind_speed:>6.02f} m/s")

    # Get the cloud, wind, and rain conditions.
    for key in ["cloud", "wind", "rain"]:
        condition = data.get(f"{key}_condition")
        condition_is_safe = data.get(f"{key}_safe")
        table.add_row(
            key.title(),
            condition.title(),
            str(condition_is_safe),
            style="green" if condition_is_safe else "red",
        )

    # Get the timestamp and format so it's readable.
    time0 = datetime.fromisoformat(data.get("timestamp"))
    td0 = datetime.now() - time0
    formatted_time = f"{time0.isoformat(sep=' ', timespec='seconds')} - ({human_readable.date_time(td0)})"
    is_time_safe = str(td0.total_seconds() < 180)
    table.add_row("Time", formatted_time, is_time_safe, style="green" if is_time_safe else "red")

    # Create a console and print the table
    console = Console()
    console.print(table)


@app.command(name="config", help="Get the configuration of the weather station.")
def config(context: typer.Context, page="config"):
    """Get the configuration of the weather station.

    This command retrieves the configuration settings from the weather station
    and prints them to the console in their raw JSON format.

    Args:
        context: The Typer context object containing the host information
        page: The API endpoint to query (defaults to 'config')

    Returns:
        None: This function prints the configuration data to the console
    """
    url = context.obj.url
    data = get_page(page, url)
    print(data)


def get_page(page, base_url):
    """Get JSON data from the specified page on the weather station.

    This function makes an HTTP request to the weather station API and returns
    the JSON response. It handles various error conditions that might occur
    during the request, providing helpful error messages and suggestions.

    Args:
        page: The endpoint to access (e.g., 'status', 'config')
        base_url: The base URL of the weather station

    Returns:
        dict: The parsed JSON data from the response

    Raises:
        SystemExit: If the request fails for any reason, with appropriate error
                   messages printed to the console before exiting

    Note:
        This function has a timeout of 10 seconds for the HTTP request.
        If the request times out or fails, it will print a helpful error
        message with possible reasons and solutions before exiting.
    """
    url = f"{base_url}/{page}"
    console = Console()

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()  # Raise an exception for HTTP errors
        return response.json()
    except requests.exceptions.ConnectionError:
        console.print(
            f"[bold red]Error:[/bold red] Could not connect to the weather station at [bold]{url}[/bold]"
        )
        console.print("[yellow]Possible reasons:[/yellow]")
        console.print("  • The weather station service is not running")
        console.print("  • The host or port is incorrect")
        console.print("  • Network connectivity issues")
        console.print("\n[green]Try:[/green]")
        console.print(
            "  • Running [bold]supervisorctl status pocs-weather-reader[/bold] to check "
            "if the service is running"
        )
        console.print("  • Running [bold]weather restart[/bold] to restart the weather service")
        console.print("  • Checking your network connection")
        exit(1)
    except requests.exceptions.Timeout:
        console.print(f"[bold red]Error:[/bold red] Request to [bold]{url}[/bold] timed out")
        console.print("[yellow]Possible reasons:[/yellow]")
        console.print("  • The weather station service is overloaded")
        console.print("  • Network connectivity issues")
        console.print("\n[green]Try:[/green]")
        console.print("  • Running [bold]weather restart[/bold] to restart the weather service")
        console.print("  • Trying again later")
        exit(1)
    except requests.exceptions.HTTPError as e:
        console.print(f"[bold red]Error:[/bold red] HTTP error occurred: [bold]{e}[/bold]")
        console.print(f"  URL: [bold]{url}[/bold]")
        exit(1)
    except requests.exceptions.RequestException as e:
        console.print(f"[bold red]Error:[/bold red] An unexpected error occurred: [bold]{e}[/bold]")
        console.print(f"  URL: [bold]{url}[/bold]")
        exit(1)
    except ValueError:
        console.print(f"[bold red]Error:[/bold red] Invalid JSON response from [bold]{url}[/bold]")
        console.print("[yellow]Possible reasons:[/yellow]")
        console.print("  • The weather station service is not functioning correctly")
        console.print("  • The response format has changed")
        console.print("\n[green]Try:[/green]")
        console.print("  • Running [bold]weather restart[/bold] to restart the weather service")
        exit(1)


@app.command(name="setup")
def setup_weather(
    power_cycle: Annotated[
        bool,
        typer.Option(
            help="Attempt to power-cycle the weather station via the power service before detection.",
        ),
    ] = False,
    power_host: str = typer.Option("localhost", help="Power service host for power-cycling."),
    power_port: str = typer.Option("6564", help="Power service port for power-cycling."),
    relay: str = typer.Option("weather_station", help="Power relay label for the weather station."),
    wait: int = typer.Option(5, help="Seconds to wait between power off and power on during power-cycle."),
    timeout: int = typer.Option(30, help="Seconds to wait for the device to appear after power-on."),
):
    """Set up the weather station udev rules for persistent device naming.

    This command detects the weather station USB serial device and writes a udev
    rule that creates a stable ``/dev/weather`` symlink.  Detection works by
    snapshotting the available serial ports, optionally power-cycling the station,
    and then watching for a newly-appeared port.

    The generated rule file is written to ``/etc/udev/rules.d/`` via ``sudo``,
    then ``udevadm`` is invoked to reload rules so the symlink is created
    immediately on the next plug-in.

    Args:
        power_cycle: When True, toggle the relay named ``relay`` off then on via
            the power service at ``power_host:power_port`` before detecting the
            device.
        power_host: Hostname or IP address of the running power service.
        power_port: TCP port of the running power service.
        relay: Label (or index) of the power relay connected to the weather
            station.
        wait: Seconds to wait with the relay off before turning it back on.
        timeout: Seconds to wait for the new serial device to appear.

    Returns:
        None
    """
    console = Console()

    # ------------------------------------------------------------------
    # Snapshot ports that already exist before we do anything.
    # ------------------------------------------------------------------
    before_ports = {p.device for p in get_serial_port_info()}

    # ------------------------------------------------------------------
    # Power-cycle via the power service if requested.
    # ------------------------------------------------------------------
    if power_cycle:
        power_url = f"http://{power_host}:{power_port}/control"
        console.print(f"[cyan]Power-cycling relay [bold]{relay}[/bold] via {power_url}...[/cyan]")
        try:
            resp = requests.post(power_url, json={"relay": relay, "command": "turn_off"}, timeout=10)
            if not resp.ok:
                console.print(f"[yellow]Warning: power-off returned {resp.status_code}.[/yellow]")
        except requests.exceptions.ConnectionError:
            console.print(
                f"[yellow]Warning: could not reach power service at {power_url}. "
                "Continuing without power-cycle.[/yellow]"
            )
        else:
            console.print(f"[dim]Waiting {wait}s with relay off...[/dim]")
            time.sleep(wait)
            try:
                resp = requests.post(power_url, json={"relay": relay, "command": "turn_on"}, timeout=10)
                if not resp.ok:
                    console.print(f"[yellow]Warning: power-on returned {resp.status_code}.[/yellow]")
                else:
                    console.print("[green]Relay back on.[/green]")
            except requests.exceptions.ConnectionError:
                console.print(
                    f"[yellow]Warning: could not reach power service at {power_url} for power-on.[/yellow]"
                )
    else:
        console.print(
            "[bold yellow]Please power-cycle the weather station now.[/bold yellow]\n"
            "You can do this by running:\n"
            f"  [cyan]pocs power off {relay} && pocs power on {relay}[/cyan]\n"
            "or by manually unplugging and re-plugging the USB cable."
        )
        typer.confirm("Press Enter once the weather station has been power-cycled", default=True)

    # ------------------------------------------------------------------
    # Poll for a new serial port to appear.
    # ------------------------------------------------------------------
    new_port = None
    deadline = time.monotonic() + timeout
    with console.status(f"Waiting up to {timeout}s for a new serial device...", spinner="dots"):
        while time.monotonic() < deadline:
            current_ports = {p.device for p in get_serial_port_info()}
            new_devices = current_ports - before_ports
            if new_devices:
                new_device = new_devices.pop()
                # Find the full port info object.
                for p in get_serial_port_info():
                    if p.device == new_device:
                        new_port = p
                        break
                break
            time.sleep(1)

    if new_port is None:
        console.print(
            f"[bold red]No new serial device detected within {timeout}s.[/bold red]\n"
            "Please check that the weather station is connected and powered on,\n"
            "then run this command again."
        )
        raise typer.Exit(code=1)

    console.print(f"[green]Detected new device:[/green] [bold]{new_port.device}[/bold]")
    if new_port.description:
        console.print(f"  Description : {new_port.description}")
    if new_port.manufacturer:
        console.print(f"  Manufacturer: {new_port.manufacturer}")

    # ------------------------------------------------------------------
    # Build the udev rule string.
    # ------------------------------------------------------------------
    if new_port.vid is None or new_port.pid is None:
        console.print(
            "[bold red]Could not read USB vendor/product ID from the device.[/bold red]\n"
            "The udev rule requires idVendor and idProduct; these are only\n"
            "available for USB-attached devices."
        )
        raise typer.Exit(code=1)

    udev_str = (
        f'ACTION=="add", '
        f'SUBSYSTEM=="tty", '
        f'ATTRS{{idVendor}}=="{new_port.vid:04x}", '
        f'ATTRS{{idProduct}}=="{new_port.pid:04x}", '
    )
    if new_port.serial_number:
        udev_str += f'ATTRS{{serial}}=="{new_port.serial_number}", '
    udev_str += 'SYMLINK+="weather"\n'

    console.print("\n[bold]udev rule that will be written:[/bold]")
    console.print(f"  [cyan]{udev_str.strip()}[/cyan]\n")

    # ------------------------------------------------------------------
    # Write the rule file via sudo.
    # ------------------------------------------------------------------
    udev_rules_name = "92-panoptes-weather.rules"
    udev_rules_dest = Path(f"/etc/udev/rules.d/{udev_rules_name}")

    try:
        subprocess.run(
            ["sudo", "tee", str(udev_rules_dest)],
            input=udev_str.encode(),
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as exc:
        console.print(
            f"[bold red]Failed to write udev rule to {udev_rules_dest}.[/bold red]\n"
            f"  {exc.stderr.decode().strip()}"
        )
        raise typer.Exit(code=1)

    console.print(f"Wrote udev rule to [green]{udev_rules_dest}[/green].")

    # ------------------------------------------------------------------
    # Reload udev rules so the symlink is active on next plug-in.
    # ------------------------------------------------------------------
    try:
        subprocess.run(["sudo", "udevadm", "control", "--reload"], check=True)
        console.print(
            "[green]✅ udev rules reloaded.[/green] Unplug and re-plug the weather station "
            "to activate the [bold]/dev/weather[/bold] symlink."
        )
    except subprocess.CalledProcessError as exc:
        console.print(
            f"[yellow]Warning: failed to reload udev rules: {exc}[/yellow]\n"
            "Run [bold]sudo udevadm control --reload[/bold] manually."
        )

    # ------------------------------------------------------------------
    # Optionally update the config server.
    # ------------------------------------------------------------------
    try:
        from panoptes.utils.config.client import set_config

        set_config("environment.weather.serial_port", "/dev/weather")
        console.print("[green]Updated config:[/green] environment.weather.serial_port → /dev/weather")
    except Exception as exc:
        console.print(
            f"[yellow]Could not update config server ({exc}). "
            "You may need to set environment.weather.serial_port to /dev/weather manually.[/yellow]"
        )


@app.command(help="Restart the weather station service via supervisorctl")
def restart(service: str = "pocs-weather-reader"):
    """Restart the weather station service via supervisorctl.

    This command uses the supervisorctl utility to restart the specified service.
    It's useful when the weather station service is not responding or needs to be
    refreshed after configuration changes.

    Args:
        service: The name of the service to restart (defaults to 'pocs-weather-reader')

    Returns:
        None: This function executes the restart command and prints the command being run

    Note:
        This command requires that supervisor is installed and configured on the system,
        and that the user has appropriate permissions to restart services.
    """
    cmd = f"supervisorctl restart {service}"
    print(f"Running: {cmd}")
    subprocess.run(cmd, shell=True)


if __name__ == "__main__":
    app()
