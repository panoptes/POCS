import serial
import typer
from rich import print
from typing_extensions import Annotated

from panoptes.utils.serial.device import get_serial_port_info
from panoptes.pocs.mount import create_mount_from_config

app = typer.Typer()


@app.command(name='park')
def park_mount(
        confirm: Annotated[bool, typer.Option(..., '--confirm',
                                              prompt='Are you sure you want to park the mount?',
                                              help='Confirm mount parking.')] = False):
    """Parks the mount.

    Warning: This will move the mount to the park position but will not do any safety
    checking. Please make sure the mount is safe to park before running this command.
    """
    if not confirm:
        print('[red]Cancelled.[/red]')
        return typer.Abort()

    mount = create_mount_from_config()
    mount.initialize()
    mount.unpark()
    mount.park()


@app.command(name='slew-home')
def search_for_home(
        confirm: Annotated[bool, typer.Option(..., '--confirm',
                                              prompt='Are you sure you want to slew to the home position?',
                                              help='Confirm slew to home.')] = False):
    """Slews the mount home position.

    Warning: This will move the mount to the home position but will not do any safety
    checking. Please make sure the mount is safe to move before running this command.
    """
    if not confirm:
        print('[red]Cancelled.[/red]')
        return typer.Abort()

    mount = create_mount_from_config()
    mount.initialize()
    mount.unpark()
    mount.slew_to_home(blocking=True)
    mount.disconnect()


@app.command(name='search-home')
def search_for_home(
        confirm: Annotated[bool, typer.Option(..., '--confirm',
                                              prompt='Are you sure you want to search for home?',
                                              help='Confirm mount searching for home.')] = False):
    """Searches for the mount home position.

    Warning: This will move the mount to the home position but will not do any safety
    checking. Please make sure the mount is safe to move before running this command.
    """
    if not confirm:
        print('[red]Cancelled.[/red]')
        return typer.Abort()

    mount = create_mount_from_config()
    mount.initialize()
    mount.search_for_home()
    mount.disconnect()


@app.command(name='setup')
def setup_mount(
        confirm: Annotated[bool, typer.Option(..., '--confirm',
                                              prompt='Are you sure you want to setup the mount?',
                                              help='Confirm mount setup.')] = False,
):
    """Sets up the mount port, type, and firmware."""
    if not confirm:
        print('[red]Cancelled.[/red]')
        return typer.Abort()

    # Baudrates to check.
    baudrates = [9600, 115200]

    # Get all the ports.
    ports = get_serial_port_info()

    # Loop through all the ports and baudrates.
    for port in ports:
        for baudrate in baudrates:
            print(f"Trying {port} at {baudrate} baud...")

            device = serial.serial_for_url(port, baudrate=baudrate, timeout=1)
            device.write(b':MountInfo#')
            response = device.readline()
            if response > '':
                print(f"Found mount at {port} at {baudrate} baud.")
                print(f"Response: {response}")

                # Get the firmware version.
                device.write(b':FW1#')
                response = device.readline()
                print(f"Firmware 1: {response}")

                device.write(b':FW2#')
                response = device.readline()
                print(f"Firmware 2: {response}")
