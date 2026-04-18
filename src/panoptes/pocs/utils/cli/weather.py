"""Typer CLI for interacting with the PANOPTES weather station service.

Provides commands to query status/config, restart the service, and set up
the weather station udev rules for persistent device naming.
"""

import glob as _glob
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import human_readable
import requests
import serial
import serial.tools.list_ports
import typer
from rich import print
from rich.console import Console
from rich.table import Table


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
    port_glob: str = typer.Option("/dev/ttyUSB*", help="Glob pattern for USB serial ports to scan."),
    baud_rate: int = typer.Option(9600, help="Baud rate for the weather station serial port."),
    read_timeout: float = typer.Option(2.0, help="Read timeout in seconds when probing each port."),
):
    """Scan USB serial ports for an AAG CloudWatcher and write a udev rule.

    Each port matching ``port_glob`` is opened and sent the AAG
    ``GET_INTERNAL_NAME`` command (``A!``).  A port that responds with the
    expected ``!N `` response code is identified as the weather station.

    Once found, a udev rule is written to
    ``/etc/udev/rules.d/92-panoptes-weather.rules`` that creates a stable
    ``/dev/weather`` symlink keyed on the device's USB vendor ID, product ID,
    and serial number (when present).  ``udevadm`` is then called to reload
    rules immediately.

    The config server key ``environment.weather.serial_port`` is updated to
    ``/dev/weather`` if the config server is reachable.

    Args:
        port_glob: Shell glob for candidate ports, e.g. ``/dev/ttyUSB*``.
        baud_rate: Serial baud rate; the AAG CloudWatcher uses 9600.
        read_timeout: Per-port read timeout in seconds.

    Returns:
        None
    """
    console = Console()

    # ------------------------------------------------------------------
    # Enumerate candidate ports.
    # ------------------------------------------------------------------
    port_paths = sorted(_glob.glob(port_glob))
    if not port_paths:
        console.print(f"[bold red]No devices found matching {port_glob!r}.[/bold red]")
        raise typer.Exit(code=1)

    console.print(f"Scanning {len(port_paths)} port(s): {', '.join(port_paths)}")

    # Build a VID/PID/serial map from pyserial's port enumeration.
    port_info_map = {p.device: p for p in serial.tools.list_ports.comports()}

    # Resolve /dev/mount symlink so we can skip that port during probing.
    mount_device: str | None = None
    mount_symlink = Path("/dev/mount")
    if mount_symlink.is_symlink():
        try:
            mount_device = str(mount_symlink.resolve())
            console.print(f"[dim]/dev/mount → {mount_device}; skipping that port[/dim]")
        except OSError:
            pass

    # ------------------------------------------------------------------
    # Probe each port for the AAG handshake.
    # ------------------------------------------------------------------
    found_device: str | None = None
    for device in port_paths:
        if mount_device and Path(device).resolve() == Path(mount_device):
            console.print(f"  Skipping [cyan]{device}[/cyan] (in use by mount)")
            continue
        console.print(f"  Trying [cyan]{device}[/cyan]...", end=" ")
        try:
            with serial.Serial(device, baudrate=baud_rate, timeout=read_timeout) as ser:
                ser.reset_input_buffer()
                ser.reset_output_buffer()
                # AAG GET_INTERNAL_NAME: command value 'A' + delimiter '!'
                ser.write(b"A!")
                response = ser.read(30)
            if b"!N " in response:
                console.print("[green]AAG CloudWatcher detected![/green]")
                found_device = device
                break
            else:
                console.print("[dim]no response[/dim]")
        except serial.SerialException as exc:
            console.print(f"[dim]error: {exc}[/dim]")
        except Exception as exc:
            console.print(f"[dim]unexpected error: {exc}[/dim]")

    if found_device is None:
        console.print(
            "[bold red]AAG CloudWatcher not found on any scanned port.[/bold red]\n"
            "Make sure the weather station is connected and powered on."
        )
        raise typer.Exit(code=1)

    # ------------------------------------------------------------------
    # Retrieve USB VID / PID / serial number for the udev rule.
    # ------------------------------------------------------------------
    port_info = port_info_map.get(found_device)
    if port_info is None:
        resolved_found_device = str(Path(found_device).resolve())
        if resolved_found_device != found_device:
            port_info = port_info_map.get(resolved_found_device)
    if port_info is None or port_info.vid is None or port_info.pid is None:
        console.print(
            "[bold red]Could not read USB vendor/product ID from the device.[/bold red]\n"
            "The udev rule requires idVendor and idProduct; these are only\n"
            "available for USB-attached devices."
        )
        raise typer.Exit(code=1)

    if port_info.description:
        console.print(f"  Description : {port_info.description}")
    if port_info.manufacturer:
        console.print(f"  Manufacturer: {port_info.manufacturer}")

    # ------------------------------------------------------------------
    # Build the udev rule string.
    # ------------------------------------------------------------------
    udev_str = (
        f'ACTION=="add", '
        f'SUBSYSTEM=="tty", '
        f'ATTRS{{idVendor}}=="{port_info.vid:04x}", '
        f'ATTRS{{idProduct}}=="{port_info.pid:04x}", '
    )
    if port_info.serial_number:
        udev_str += f'ATTRS{{serial}}=="{port_info.serial_number}", '
    udev_str += 'SYMLINK+="weather"\n'

    console.print("\n[bold]udev rule to be written:[/bold]")
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
    # Reload udev rules so the symlink is active on the next plug-in.
    # ------------------------------------------------------------------
    try:
        subprocess.run(
            ["sudo", "udevadm", "control", "--reload"],
            check=True,
            capture_output=True,
            text=True,
        )
        console.print(
            "[green]✅ udev rules reloaded.[/green] Unplug and re-plug the weather station "
            "to activate the [bold]/dev/weather[/bold] symlink."
        )
    except subprocess.CalledProcessError as exc:
        error_output = (exc.stderr or "").strip()
        stdout_output = (exc.stdout or "").strip()
        details = error_output or stdout_output
        detail_message = f"\n  {details}" if details else ""
        console.print(
            f"[yellow]Warning: failed to reload udev rules: {exc}[/yellow]{detail_message}\n"
            "Run [bold]sudo udevadm control --reload[/bold] manually."
        )

    # ------------------------------------------------------------------
    # Update the config server if reachable.
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
