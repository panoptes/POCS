import os

import typer
from panoptes.utils.time import current_time
from panoptes.utils.utils import altaz_to_radec
from rich import print
from typing import List
from typing_extensions import Annotated

from panoptes.pocs.core import POCS
from panoptes.pocs.mount.mount import AbstractMount as Mount
from panoptes.pocs.mount import create_mount_from_config
from panoptes.pocs.scheduler.field import Field
from panoptes.pocs.scheduler.observation.base import Observation

app = typer.Typer()


@app.callback()
def common(context: typer.Context,
           simulator: List[str] = typer.Option(None, '--simulator', '-s', help='Simulators to load')
           ):
    context.obj = simulator


def get_pocs(context: typer.Context):
    """Helper to get pocs after confirming with user."""
    simulators = context.obj
    confirm = typer.prompt('Are you sure you want to run POCS automatically?', default='n')
    if confirm.lower() not in ['y', 'yes']:
        raise typer.Abort()

    # Change to home directory.
    os.chdir(os.path.expanduser('~'))

    print(f'Running POCS with simulators: {simulators=}')
    print('[green]Running POCS automatically![/green]\n'
          '[bold green]Press Ctrl-c to quit.[/bold green]')

    pocs = POCS.from_config(simulators=simulators)
    pocs.initialize()

    return pocs


@app.command(name='auto')
def run_auto(context: typer.Context) -> None:
    """Runs POCS automatically, like it's meant to be run."""

    pocs = get_pocs(context)

    try:
        pocs.run()
    except KeyboardInterrupt:
        print('[red]POCS interrupted by user, shutting down.[/red]')
    except Exception as e:
        print('[bold red]POCS encountered an error.[/bold red]')
        print(e)
    else:
        print('[green]POCS finished, shutting down.[/green]')
    finally:
        print(f'[bold yellow]Please be patient, this may take a moment while the mount parks itself.[/bold yellow]')
        pocs.power_down()


@app.command(name='alignment')
def run_alignment(context: typer.Context,
                  coords: List[str] = typer.Option(None, '--coords', '-c',
                                                   help='Alt/Az coordinates to use, e.g. 40,55'),
                  exptime: float = 30,
                  num_exposures: int = 10,
                  field_name: str = 'PolarAlignment',
                  move_mount=True,
                  ) -> None:
    """Runs POCS in alignment mode.

    Not specifying coordinates is the same as the following:
        -c 40,90 -c 55,60 -c 55,120 -c 70,210 -c 70,330
    """
    pocs = get_pocs(context)

    altaz_coords = coords or [
        # (alt, az)
        (40, 90),
        (55, 60),
        (55, 120),
        (70, 210),
        (70, 330),
    ]
    print(f'Using {altaz_coords=} for alignment.')

    # Helper function to make an observation from altaz coordinates.
    def get_altaz_observation(coords, seq_time) -> Observation:
        alt, az = coords
        coord = altaz_to_radec(alt, az, pocs.observatory.earth_location, current_time())
        alignment_observation = Observation(Field(field_name, coord),
                                            exptime=exptime,
                                            min_nexp=num_exposures,
                                            exp_set_size=num_exposures)
        alignment_observation.seq_time = seq_time

        return alignment_observation

    # Start the polar alignment sequence.
    mount = pocs.observatory.mount

    try:
        # Shared sequence time for all alignment observations.
        sequence_time = current_time(flatten=True)

        for i, altaz_coord in enumerate(altaz_coords):
            print(f'Starting coord #{i:02d}/{num_exposures:02d} {altaz_coord=}')

            # Create an observation and set it as current.
            observation = get_altaz_observation(altaz_coord, sequence_time)
            pocs.observatory.current_observation = observation

            if move_mount:
                print(f'Slewing to RA/Dec {observation.field.coord.to_string()} for {altaz_coord=}')
                mount.unpark()
                mount.set_target_coordinates(observation.field.coord)
                mount.slew_to_target(blocking=True)

            # Take all the exposures for this altaz observation.
            pocs.observe_target(observation=observation, blocking=True)
    except KeyboardInterrupt:
        print('[red]POCS alignment interrupted by user, shutting down.[/red]')
    except Exception as e:
        print('[bold red]POCS encountered an error.[/bold red]')
        print(e)
    else:
        print('[green]POCS alignment finished, shutting down.[/green]')
    finally:
        print(f'[bold yellow]Please be patient, this may take a moment while the mount parks itself.[/bold yellow]')
        pocs.power_down()


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
    do_mount_command(mount, 'park')


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
    do_mount_command(mount, 'slew_to_home')


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
    do_mount_command(mount, 'search_for_home')


def do_mount_command(mount: Mount, cmd_name: str):
    """Perform a mount command."""
    try:
        cmd = getattr(mount, cmd_name)
        print(f'Running {cmd_name} on mount, please be patient.')
        cmd()
    except KeyboardInterrupt:
        print('[red]Mount parking interrupted by user.[/red]')
    except Exception as e:
        print('[bold red]Mount encountered an error.[/bold red]')
        print(e)
    else:
        print('[green]Mount parking finished.[/green]')
    finally:
        mount.disconnect()
