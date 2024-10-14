import re
from pathlib import Path

import serial
import typer
from astropy import units as u
from astropy.coordinates import AltAz, SkyCoord
from astropy.coordinates.name_resolve import NameResolveError
from human_readable import time_delta as friendly_time_delta
from panoptes.utils.config.client import set_config
from panoptes.utils.rs232 import SerialData
from panoptes.utils.serial.device import get_serial_port_info
from panoptes.utils.time import current_time
from rich import print
from typing_extensions import Annotated

from panoptes.pocs.mount import create_mount_from_config
from panoptes.pocs.mount.ioptron import MountInfo
from panoptes.pocs.utils.location import create_location_from_config

app = typer.Typer()


@app.command(name='park')
def park_mount(
    confirm: Annotated[bool, typer.Option(
        ..., '--confirm',
        prompt='Are you sure you want to park the mount?',
        help='Confirm mount parking.'
    )] = False
):
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


@app.command(name='set-park')
def set_park_position(
    confirm: Annotated[bool, typer.Option(
        ..., '--confirm',
        prompt='Are you sure you want to set the park position?',
        help='Confirm setting the park position.'
    )] = False
):
    """Sets the park position.

    Warning: This will move the mount to the park position but will not do any safety
    checking. Please make sure the mount is safe to move before running this command.
    """
    if not confirm:
        print('[red]Cancelled.[/red]')
        return typer.Abort()

    mount = create_mount_from_config()
    mount.initialize()

    # Confirm that they have previously set the home position.
    if not typer.confirm('Have you previously set the home position?'):
        print('Please set the home position before setting the park position by running "pocs mount search-home".')
        return typer.Exit()

    print(f'The mount will first park at the default position and then ask you to confirm the new park position.')
    mount.unpark()
    mount.park()

    # Check if correct side of the pier (i.e. RA axis).
    if not typer.confirm('Is the mount on the correct side of the pier?'):
        # Switch the RA axis.
        old_ra_direction = mount.get_config('mount.settings.park.ra_direction')
        new_ra_direction = 'east' if old_ra_direction == 'west' else 'west'
        mount.set_config('mount.settings.park.ra_direction', new_ra_direction)
        print(f'Changed RA direction from {old_ra_direction} to {new_ra_direction}.')
        print('Sending the mount home to try the parking again.')
        mount.unpark()
        mount.slew_to_home(blocking=True)
        mount.park()

    # Check to make sure cameras are facing down (i.e. Dec axis).
    if not typer.confirm('Are the cameras facing down?'):
        # Switch the DEC axis.
        old_dec_direction = mount.get_config('mount.settings.park.dec_direction')
        new_dec_direction = 'north' if old_dec_direction == 'south' else 'south'
        mount.set_config('mount.settings.park.dec_direction', new_dec_direction)
        print(f'Changed Dec direction from {old_dec_direction} to {new_dec_direction}.')
        print('Sending the mount home to try the parking again.')
        mount.unpark()
        mount.slew_to_home(blocking=True)
        mount.park()

    # Double-check the park position.
    if not typer.confirm('Is the mount parked in the correct position?'):
        # Give warning and bail out.
        print('[red]Sorry! Please try again or ask the PANOPTES team.[/red]')
    else:
        print(
            'Park position set. If the directions are correct but the mount is not parked in the correct position, '
            'then you may need to adjust the number of seconds the mount moves in each direction. If you are unsure, '
            'please ask the PANOPTES team for help.'
        )


@app.command(name='slew-home')
def slew_to_home(
    confirm: Annotated[bool, typer.Option(
        ..., '--confirm',
        prompt='Are you sure you want to slew to the home position?',
        help='Confirm slew to home.'
    )] = False
):
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


@app.command(name='slew-to-target')
def slew_to_target(
    confirm: Annotated[bool, typer.Option(
        ..., '--confirm',
        prompt='Are you sure you want to slew to the target position?',
        help='Confirm slew to target.'
    )] = False,
    target: Annotated[str, typer.Option(
        ..., '--target', '-t',
        prompt='The name of the target to slew the mount to.',
        help='The name of the target to slew the mount to.'
    )] = None,
    dry_run: Annotated[bool, typer.Option(
        ..., '--dry-run',
        help="Show target info but don't actually initialize or move the mount."
    )] = False,
):
    """Slews the mount target position."""
    if not confirm:
        print('[red]Cancelled.[/red]')
        return typer.Abort()

    print(f'Looking for coordinates for {target}.')
    coords = None
    try:
        coords = SkyCoord(target)
    except ValueError:
        try:
            coords = SkyCoord.from_name(target)
        except NameResolveError:
            pass
    finally:
        if not coords:
            print(f'[red]Could not find a suitable target by name or position.[/red]')
            return typer.Abort()

    # Get the observer location
    location = create_location_from_config()

    print(f'Using {coords=} from {location.observer.name}')

    # Check that the target is observable.
    is_observable = location.observer.target_is_up(current_time(), coords, horizon=30. * u.deg)
    if not is_observable:
        print(f'[red]Target is not observable[/red]')
        return typer.Abort()

    # Show target info for observatory.
    target_set_time = location.observer.target_set_time(current_time(), coords, horizon=30. * u.deg, which='next')
    print(
        f'Target will be above 30° for '
        f'{friendly_time_delta(current_time().to_datetime(), target_set_time.to_datetime())}'
    )

    # Get AltAz for coordinates.
    alt_az = coords.transform_to(AltAz(location=location.earth_location, obstime=current_time()))
    print(f'Current position: Alt={alt_az.alt:.02f} Az={alt_az.az:.02f}')

    if dry_run:
        print(f'[red]Dry run, will not move the mount.[/red]')
        return typer.Abort()

    mount = create_mount_from_config()
    mount.initialize()
    mount.set_target_coordinates(coords)
    mount.slew_to_target(blocking=True)

    # TODO create a watchdog for park/safety?

    mount.disconnect()


@app.command(name='search-home')
def search_for_home(
    confirm: Annotated[bool, typer.Option(
        ..., '--confirm',
        prompt='Are you sure you want to search for home?',
        help='Confirm mount searching for home.'
    )] = False
):
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
    confirm: Annotated[bool, typer.Option(
        ..., '--confirm',
        prompt='Are you sure you want to setup the mount?',
        help='Confirm mount setup.'
    )] = False,
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
        if 'ttyUSB' not in port.device:
            continue
        for baudrate in baudrates:
            print(f"Trying {port.device=} at {baudrate=}...")
            device = SerialData(port=port.device, baudrate=baudrate, timeout=1)

            try:
                device.write(':MountInfo#')
                try:
                    response = device.read()
                except serial.SerialException:
                    print('\tDevice potentially being accessed by another process.')
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

                    write_port = port.device

                    if typer.confirm('Do you want to make a udev entry?'):
                        print('Creating udev entry for device')
                        # Get info for writing udev entry.
                        try:
                            udev_str = (
                                f'ACTION=="add", '
                                f'SUBSYSTEM=="tty", '
                                f'ATTRS{{idVendor}}=="{port.vid:04x}", '
                                f'ATTRS{{idProduct}}=="{port.pid:04x}", '
                            )
                            if port.serial_number is not None:
                                udev_str += f'ATTRS{{serial}}=="{port.serial_number}", '

                            # The name we want it known by.
                            udev_str += f'SYMLINK+="ioptron"'

                            udev_fn = Path('91-panoptes.rules')
                            with udev_fn.open('w') as f:
                                f.write(udev_str)

                            write_port = '/dev/ioptron'

                            print(f'Wrote udev entry to [green]{udev_fn}[/green].')
                            print('Run the following command and then reboot for changes to take effect:')
                            print(f'\t[green]cat {udev_fn} | sudo tee /etc/udev/rules.d/{udev_fn}[/green]')
                        except Exception:
                            pass

                    # Confirm the user wants to update the config.
                    if typer.confirm('Do you want to update the config?'):
                        print('Updating config.')
                        set_config('mount.brand', 'ioptron')
                        set_config('mount.serial.port', write_port)
                        set_config('mount.serial.baudrate', baudrate)
                        set_config('mount.model', mount_type.name.lower())
                        set_config('mount.driver', f'panoptes.pocs.mount.ioptron.{mount_type.name.lower()}')
                        set_config('mount.commands_file', f'ioptron/{command_set}')

                    return typer.Exit()
            except serial.SerialTimeoutException:
                pass
