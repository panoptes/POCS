import os

import typer
from panoptes.utils.time import current_time
from panoptes.utils.utils import altaz_to_radec
from rich import print
from typing import List
from typing_extensions import Annotated

from panoptes.pocs.core import POCS
from panoptes.pocs.scheduler.field import Field
from panoptes.pocs.scheduler.observation.base import Observation

app = typer.Typer()


@app.command(name='auto')
def run_auto(confirm: Annotated[bool, typer.Option(prompt='Are you sure you want to run POCS automatically?')],
             simulator: List[str] = typer.Option(..., '--simulator', '-s', help='Simulators to load')) -> None:
    """Runs POCS automatically, like it's meant to be run."""

    print(f'Running POCS with simulators: {simulator=}')
    print()

    if confirm is True:
        # Change to home directory.
        os.chdir(os.path.expanduser('~'))
        print('[green]Running POCS automatically!\t[bold]Press Ctrl-c to quit.[/bold][/green]')
        pocs = POCS.from_config(simulators=simulator)
        pocs.initialize()

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
def run_alignment(confirm: Annotated[
    bool, typer.Option(prompt='Are you sure you want to run the polar alignment script?')],
                  simulator: List[str] = typer.Option(..., '--simulator', '-s', help='Simulators to load'),
                  exptime: float = 30,
                  num_exposures: int = 10,
                  field_name: str = 'PolarAlignment',
                  move_mount=True,
                  ) -> None:
    """Runs POCS in alignment mode."""
    if confirm is False:
        print('Exit.')
        raise typer.Abort()

    altaz_coords = [
        # (alt, az)
        (40, 90),
        (55, 60),
        (55, 120),
        (70, 210),
        (70, 330),
    ]

    # Helper function to make an observation from altaz coordinates.
    def get_altaz_observation(coords) -> Observation:
        alt, az = coords
        coord = altaz_to_radec(alt, az, pocs.observatory.earth_location, current_time())
        alignment_observation = Observation(Field(field_name, coord),
                                            exptime=exptime,
                                            min_nexp=num_exposures,
                                            exp_set_size=num_exposures)

        return alignment_observation

    # Change to home directory.
    os.chdir(os.path.expanduser('~'))
    print('[green]Running POCS in alignment mode!\t[bold]Press Ctrl-c to quit.[/bold][/green]')
    pocs = POCS.from_config(simulators=simulator)
    pocs.initialize()

    # Start the polar alignment sequence.
    mount = pocs.observatory.mount

    try:
        sequence_time = current_time(flatten=True)
        for i, altaz_coord in enumerate(altaz_coords):
            print(f'Starting coord #{i:02d}/{num_exposures:02d} {altaz_coord=}')
            observation = get_altaz_observation(altaz_coord)
            observation.seq_time = sequence_time
            pocs.observatory.current_observation = observation

            if move_mount:
                mount.unpark()
                print(f'Slewing to RA/Dec {observation.field.coord.to_string()} for {altaz_coord=}')
                mount.set_target_coordinates(observation.field.coord)
                mount.slew_to_target(blocking=True)

            # Take the observation.
            pocs.observatory.take_observation(blocking=True)
            print()
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
