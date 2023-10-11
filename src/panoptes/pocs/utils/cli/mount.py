import re

import serial
import typer
from panoptes.utils.config.client import set_config
from rich import print
from typing_extensions import Annotated

from panoptes.utils.serial.device import get_serial_port_info
from panoptes.utils.rs232 import SerialData
from panoptes.pocs.mount import create_mount_from_config
from panoptes.pocs.mount.ioptron import MountInfo

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

    # Get all the serial ports.
    ports = get_serial_port_info()

    # Loop through all the ports and baudrates.
    for port in ports:
        for baudrate in baudrates:
            if 'serial' in port.device or 'aag' in port.device:
                continue
            print(f"Trying {port.device=} at {baudrate=}...")
            device = SerialData(port=port.device, baudrate=baudrate, timeout=1)

            try:
                device.write(':MountInfo#')
                try:
                    response = device.read()
                except serial.SerialException:
                    print('Device potentially being accessed by another process.')
                    continue

                if re.match(r'\d{4}', response):  # iOptron specific
                    mount_type = MountInfo(int(response[0:4]))
                    print(f'Found mount at {port.device=} at {baudrate=} with {response=}.')
                    print(f'It looks like an iOptron {mount_type.name}.')

                    # Get the mainboard and handcontroller firmware version.
                    device.write(':FW1#')
                    response = device.read()
                    mainboard_fw = int(response[:6])
                    handcontroller_fw = response[6:-1]  # Returns a string if HC not plugged in.
                    print('Firmware:')
                    print(f'\tMainboard: {mainboard_fw}')
                    print(f'\tHandcontroller: {handcontroller_fw}')

                    # Get the RA and DEC firmware version.
                    device.write(':FW2#')
                    response = device.read()
                    ra_fw = int(response[:6])
                    dec_fw = int(response[6:-1])
                    print(f'\tRA: {ra_fw}')
                    print(f'\tDEC: {dec_fw}')

                    command_set = 'v310' if ra_fw >= 210101 and dec_fw >= 210101 else 'v250'
                    print(f'Suggested command set: {command_set}')

                    # Get info for writing udev entry.
                    udev_str = (f'SUBSYSTEM="tty", '
                                f'SUBSYSTEMS=="{port.subsytem}", '
                                f'ATTRS{{idVendor}}=="{port.vid:04x}", '
                                f'ATTRS{{idProduct}}=="{port.pid:04x}", '
                                f'ATTRS{{serial}}=="{port.serial_number}", '
                                f'SYMLINK+="ioptron"')
                    print(f'UDEV entry: {udev_str}')

                    # Confirm the user wants to update the config.
                    if typer.confirm('Do you want to update the config?'):
                        print('Updating config.')
                        set_config('mount.brand', 'ioptron')
                        set_config('mount.serial.port', port.device)
                        set_config('mount.serial.baudrate', baudrate)
                        set_config('mount.model', mount_type.name.lower())
                        set_config('mount.driver', f'panoptes.pocs.mount.ioptron.{mount_type.name.lower()}')
                        set_config('mount.commands_file', f'ioptron/{command_set}')

                    return typer.Exit()
            except serial.SerialTimeoutException:
                pass
