import os
import warnings
from itertools import product
from multiprocessing import Process
from typing import List

import typer
from panoptes.utils.config.client import get_config
from panoptes.utils.time import current_time
from panoptes.utils.utils import altaz_to_radec
from rich import print

from panoptes.pocs.core import POCS
from panoptes.pocs.scheduler.field import Field
from panoptes.pocs.scheduler.observation.base import Observation

app = typer.Typer()

# Ignore FITS header warnings.
warnings.filterwarnings(action='ignore', message='datfix')


@app.callback()
def common(context: typer.Context,
           simulator: List[str] = typer.Option(None, '--simulator', '-s', help='Simulators to load'),
           cloud_logging: bool = typer.Option(False, '--cloud-logging', '-c', help='Enable cloud logging'),
           ):
    context.obj = simulator
    if cloud_logging:
        os.environ['CLOUD_LOGGING'] = 'True'
        os.environ['PANID'] = str(get_config('PANID'))


def get_pocs(context: typer.Context):
    """Helper to get pocs after confirming with user."""
    simulators = context.obj
    confirm = typer.prompt('Are you sure you want to run POCS automatically?', default='n')
    if confirm.lower() not in ['y', 'yes']:
        raise typer.Exit(0)

    # Change to home directory.
    os.chdir(os.path.expanduser('~'))

    if len(simulators) > 0:
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
                                                   help='Alt/Az coordinates to use, e.g. 40,120'),
                  exptime: float = typer.Option(30.0, '--exptime', '-e', help='Exposure time in seconds.'),
                  num_exposures: int = typer.Option(5, '--num-exposures', '-n',
                                                    help='Number of exposures per coordinate.'),
                  field_name: str = typer.Option('PolarAlignment', '--field-name', '-f', help='Name of field.'),
                  ) -> None:
    """Runs POCS in alignment mode.

    Not specifying coordinates is the same as the following:
        -c 55,60 -c 55,120 -c 55,240 -c 55,300
        -c 70,60 -c 70,120 -c 70,240 -c 70,300
    """
    pocs = get_pocs(context)

    alts = [55, 70]
    azs = [60, 120, 240, 300]

    altaz_coords = coords or list(product(alts, azs))
    altaz_coords = sorted(altaz_coords, key=lambda x: x[1])  # Sort by azimuth.
    print(f'Using {altaz_coords=} for alignment.\n')

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

        procs = list()
        for i, altaz_coord in enumerate(altaz_coords):
            print(f'{field_name} #{i:02d}/{len(altaz_coords):02d} {altaz_coord=}')

            # Create an observation and set it as current.
            observation = get_altaz_observation(altaz_coord, sequence_time)
            pocs.observatory.current_observation = observation

            print(f'\tSlewing to RA/Dec {observation.field.coord.to_string()} for {altaz_coord=}')
            mount.unpark()
            target_set = mount.set_target_coordinates(observation.field.coord)

            # If the mount can't set the target coordinates, skip this observation.
            if not target_set:
                print(f'\tInvalid coords, skipping {altaz_coord=}')
                continue

            started_slew = mount.slew_to_target(blocking=True)

            # If the mount can't slew to the target, skip this observation.
            if not started_slew:
                print(f'\tNo slew, skipping {altaz_coord=}')
                continue

            # Take all the exposures for this altaz observation.
            for j in range(num_exposures):
                print(f'\tStarting {exptime}s exposure #{j + 1:02d}/{num_exposures:02d}')
                pocs.observatory.take_observation(blocking=True)

                # Do processing in background (if exposure time is long enough).
                if exptime > 10:
                    process_proc = Process(target=pocs.observatory.process_observation)
                    process_proc.start()
                    procs.append(process_proc)

            mount.query('stop_tracking')

    except KeyboardInterrupt:
        print('[red]POCS alignment interrupted by user, shutting down.[/red]')
    except Exception as e:
        print('[bold red]POCS encountered an error.[/bold red]')
        print(e)
    else:
        print('[green]POCS alignment finished, shutting down.[/green]')
    finally:
        print(f'[bold yellow]Please be patient, this may take a moment while the mount parks itself.[/bold yellow]')
        pocs.observatory.mount.park()

        # Wait for all the processing to finish.
        print('Waiting for image processing to finish.')
        for proc in procs:
            proc.join()

        pocs.power_down()
