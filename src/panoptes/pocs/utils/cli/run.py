import os
import time
import warnings
from itertools import product
from multiprocessing import Process
from typing import List

import typer
from panoptes.utils.error import PanError
from panoptes.utils.images import make_pretty_image
from panoptes.utils.images.cr2 import cr2_to_fits
from panoptes.utils.time import current_time
from panoptes.utils.utils import altaz_to_radec, listify
from rich import print

from panoptes.pocs.core import POCS
from panoptes.pocs.scheduler.field import Field
from panoptes.pocs.scheduler.observation.base import Observation
from panoptes.pocs.utils import alignment as polar_alignment
from panoptes.pocs.utils.logger import get_logger

app = typer.Typer()

# Ignore FITS header warnings.
warnings.filterwarnings(action='ignore', message='datfix')


@app.callback()
def common(
    context: typer.Context,
    simulator: List[str] = typer.Option(None, '--simulator', '-s', help='Simulators to load'),
    cloud_logging: bool = typer.Option(False, '--cloud-logging', '-c', help='Enable cloud logging'),
):
    context.obj = [simulator, cloud_logging]


def get_pocs(context: typer.Context):
    """Helper to get pocs after confirming with user."""
    simulators, cloud_logging = context.obj
    confirm = typer.prompt('Are you sure you want to run POCS automatically?', default='n')
    if confirm.lower() not in ['y', 'yes']:
        raise typer.Exit(0)

    # Change to home directory.
    os.chdir(os.path.expanduser('~'))

    simulators = listify(simulators)

    if len(simulators) > 0:
        print(f'Running POCS with simulators: {simulators=}')

    print(
        '[green]Running POCS automatically![/green]\n'
        '[bold green]Press Ctrl-c to quit.[/bold green]'
    )

    # If cloud logging is requested, set DEBUG level, otherwise the config
    # and regular set up will handle things.
    if cloud_logging:
        logger = get_logger(cloud_logging_level='DEBUG')

    pocs = POCS.from_config(simulators=simulators)

    pocs.logger.debug(f'POCS created from config')
    pocs.logger.debug(f'Sending POCS config to cloud')
    try:
        pocs.db.insert_current('config', pocs.get_config())
    except Exception as e:
        pocs.logger.warning(f'Unable to send config to cloud: {e}')

    pocs.initialize()

    return pocs


@app.command(name='alignment')
def run_alignment(context: typer.Context) -> None:
    """Runs POCS in alignment mode."""
    pocs = get_pocs(context)
    print(f'[bold yellow]Starting POCS in alignment mode.[/bold yellow]')
    start_time = current_time(flatten=True)

    base_dir = f'/home/panoptes/images/drift_align/{start_time}'
    plot_fn = f'{base_dir}/{start_time}_center_overlay.jpg'

    mount = pocs.observatory.mount

    pocs.say("Moving to home position")
    mount.slew_to_home()

    # Polar Rotation
    pole_fn = polar_rotation(pocs, base_dir=base_dir)
    pole_fn = pole_fn.replace('.cr2', '.fits')

    # Mount Rotation
    rotate_fn = mount_rotation(pocs, base_dir=base_dir)
    rotate_fn = rotate_fn.replace('.cr2', '.fits')

    pocs.say("Moving back to home")
    mount.slew_to_home()

    pocs.say("Solving celestial pole image")
    try:
        pole_center = polar_alignment.analyze_polar_rotation(pole_fn)
    except Exception:
        print("Unable to solve pole image.")
        print("Will proceed with rotation image but analysis not possible")
        pole_center = None
    else:
        pole_center = (float(pole_center[0]), float(pole_center[1]))

    pocs.say("Starting analysis of rotation image")
    try:
        rotate_center = polar_alignment.analyze_ra_rotation(rotate_fn)
    except Exception:
        print("Unable to process rotation image")
        rotate_center = None

    if pole_center is not None and rotate_center is not None:
        pocs.say("Plotting centers")

        pocs.say(f"Pole ({pole_fn}) : {pole_center[0]:0.2f} x {pole_center[1]:0.2f}")

        pocs.say(f"Rotate: {rotate_center} {rotate_fn}")
        pocs.say(f"Rotate: {rotate_center[0]:0.2f} x {rotate_center[1]:0.2f}")

        d_x = pole_center[0] - rotate_center[0]
        d_y = pole_center[1] - rotate_center[1]

        pocs.say(f"d_x: {d_x:0.2f}")
        pocs.say(f"d_y: {d_y:0.2f}")

        fig = polar_alignment.plot_center(pole_fn, rotate_fn, pole_center, rotate_center)

        print(f"Plot image: {plot_fn}")
        fig.tight_layout()
        fig.savefig(plot_fn)

        try:
            os.unlink('/var/panoptes/images/latest.jpg')
        except Exception:
            pass
        try:
            os.symlink(plot_fn, '/var/panoptes/images/latest.jpg')
        except Exception:
            print("Can't link latest image")

        with open(f'/home/panoptes/images/drift_align/center.txt', 'a') as f:
            f.write(
                '{}.{},{},{},{},{},{}\n'.format(
                    start_time, pole_center[0], pole_center[1], rotate_center[0], rotate_center[1], d_x, d_y
                )
            )

        print("Done with polar alignment test")
        pocs.say("Done with polar alignment test")


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
def run_alignment(
    context: typer.Context,
    coords: List[str] = typer.Option(
        None, '--coords', '-c',
        help='Alt/Az coordinates to use, e.g. 40,120'
    ),
    exptime: float = typer.Option(30.0, '--exptime', '-e', help='Exposure time in seconds.'),
    num_exposures: int = typer.Option(
        5, '--num-exposures', '-n',
        help='Number of exposures per coordinate.'
    ),
    field_name: str = typer.Option('PolarAlignment', '--field-name', '-f', help='Name of field.'),
) -> None:
    """Runs POCS in alignment mode.

    Not specifying coordinates is the same as the following:
        -c 55,60 -c 55,120 -c 55,240 -c 55,300
        -c 70,60 -c 70,120 -c 70,240 -c 70,300
    """
    pocs = get_pocs(context)
    print(f'[bold yellow]Starting POCS in alignment mode.[/bold yellow]')
    pocs.update_status()

    alts = [55, 70]
    azs = [60, 120, 240, 300]

    altaz_coords = coords or list(product(alts, azs))
    altaz_coords = sorted(altaz_coords, key=lambda x: x[1])  # Sort by azimuth.
    print(f'Using {altaz_coords=} for alignment.\n')

    # Helper function to make an observation from altaz coordinates.
    def get_altaz_observation(coords, seq_time) -> Observation:
        alt, az = coords
        coord = altaz_to_radec(alt, az, pocs.observatory.earth_location, current_time())
        alignment_observation = Observation(
            Field(field_name, coord),
            exptime=exptime,
            min_nexp=num_exposures,
            exp_set_size=num_exposures
        )
        alignment_observation.seq_time = seq_time

        return alignment_observation

    # Start the polar alignment sequence.
    mount = pocs.observatory.mount

    try:
        # Shared sequence time for all alignment observations.
        sequence_time = current_time(flatten=True)

        procs = list()
        for i, altaz_coord in enumerate(altaz_coords):
            # Check safety (parking happens below if unsafe).
            if pocs.is_safe(park_if_not_safe=False) is False:
                print('[red]POCS is not safe, shutting down.[/red]')
                raise PanError('POCS is not safe.')

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
                pocs.update_status()

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
    except PanError as e:
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


def polar_rotation(pocs, exp_time=30, base_dir=None, **kwargs):
    assert base_dir is not None, print("base_dir cannot be empty")

    mount = pocs.observatory.mount

    print('Performing polar rotation test')
    pocs.say('Performing polar rotation test')
    mount.slew_to_home()

    while not mount.is_home:
        time.sleep(2)

    analyze_fn = None

    print('At home position, taking {} sec exposure'.format(exp_time))
    pocs.say('At home position, taking {} sec exposure'.format(exp_time))
    procs = dict()
    for cam_name, cam in pocs.observatory.cameras.items():
        fn = f'{base_dir}/pole_{cam_name.lower()}.cr2'
        proc = cam.take_exposure(seconds=exp_time, filename=fn)
        procs[fn] = proc
        if cam.is_primary:
            analyze_fn = fn

    for fn, proc in procs.items():
        try:
            outs, errs = proc.communicate(timeout=(exp_time + 15))
        except AttributeError:
            continue
        except KeyboardInterrupt:
            print('Pole test interrupted')
            proc.kill()
            outs, errs = proc.communicate()
            break
        except Exception:
            proc.kill()
            outs, errs = proc.communicate()
            break

        time.sleep(2)
        try:
            make_pretty_image(fn, title='Alignment Test - Celestial Pole', primary=True)
            cr2_to_fits(fn, remove_cr2=True)
        except AssertionError:
            print(f"Can't make image for {fn}")
            pocs.say(f"Can't make image for {fn}")

    return analyze_fn


def mount_rotation(pocs, base_dir=None, include_west=False, west_time=11, east_time=21, **kwargs):
    mount = pocs.observatory.mount

    print("Doing rotation test")
    pocs.say("Doing rotation test")
    mount.slew_to_home()
    exp_time = 25
    mount.move_direction(direction='west', seconds=west_time)

    rotate_fn = None

    # Start exposing on cameras
    for direction in ['east', 'west']:
        if include_west is False and direction == 'west':
            continue

        print(f"Rotating to {direction}")
        pocs.say(f"Rotating to {direction}")
        procs = dict()
        for cam_name, cam in pocs.observatory.cameras.items():
            fn = f'{base_dir}/rotation_{direction}_{cam_name.lower()}.cr2'
            proc = cam.take_exposure(seconds=exp_time, filename=fn)
            procs[fn] = proc
            if cam.is_primary:
                rotate_fn = fn

        # Move mount
        mount.move_direction(direction=direction, seconds=east_time)

        # Get exposures
        for fn, proc in procs.items():
            try:
                outs, errs = proc.communicate(timeout=(exp_time + 15))
            except AttributeError:
                continue
            except KeyboardInterrupt:
                print('Pole test interrupted')
                pocs.say('Pole test interrupted')
                proc.kill()
                outs, errs = proc.communicate()
                break
            except Exception:
                proc.kill()
                outs, errs = proc.communicate()
                break

            time.sleep(2)
            try:
                make_pretty_image(fn, title=f'Alignment Test - Rotate {direction}', primary=True)
                cr2_to_fits(fn, remove_cr2=True)
            except AssertionError:
                print(f"Can't make image for {fn}")
                pocs.say(f"Can't make image for {fn}")

    return rotate_fn
