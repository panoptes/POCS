import os
import time
import warnings
from collections import defaultdict
from itertools import product
from multiprocessing import Process
from numbers import Number
from pathlib import Path
from typing import List

import typer
from astropy.coordinates import SkyCoord
from panoptes.utils.error import PanError
from panoptes.utils.images import make_pretty_image
from panoptes.utils.images.cr2 import cr2_to_fits
from panoptes.utils.time import current_time
from panoptes.utils.utils import altaz_to_radec, listify
from pick import pick
from rich import print

from panoptes.pocs.core import POCS
from panoptes.pocs.scheduler.field import Field
from panoptes.pocs.scheduler.observation.base import Observation
from panoptes.pocs.utils import alignment as polar_alignment
from panoptes.pocs.utils.alignment import plot_alignment_diff, process_quick_alignment
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


@app.command(name='old-alignment')
def run_old_alignment(
    context: typer.Context,
    exp_time: float = typer.Option(30.0, '--exptime', '-e', help='Exposure time in seconds.'),
) -> None:
    """Runs POCS in alignment mode."""
    pocs = get_pocs(context)
    print(f'[bold yellow]Starting POCS in alignment mode.[/bold yellow]')
    start_time = current_time(flatten=True)

    images_dir = Path(pocs.get_config('directories.images'))
    base_dir = images_dir / 'drift_align' / str(start_time)

    plot_fn = f'{base_dir}/{start_time}_center_overlay.jpg'

    mount = pocs.observatory.mount

    try:

        mount.unpark()
        pocs.say("Moving to home position")
        mount.slew_to_home()

        # Polar Rotation
        pole_fn = polar_rotation(pocs, base_dir=base_dir, exp_time=exp_time)
        pole_fn = pole_fn.with_suffix('.fits')

        # Mount Rotation
        rotate_fn = mount_rotation(pocs, base_dir=base_dir)
        rotate_fn = rotate_fn.with_suffix('.fits')

        pocs.say("Moving back to home")
        mount.slew_to_home()

        pocs.say("Solving celestial pole image")
        try:
            pole_center = polar_alignment.get_celestial_center(pole_fn, timeout=exp_time + 15)
        except Exception as e:
            print("[bold red]Unable to solve pole image.[/bold red]")
            print("[bold yellow]Will proceed with rotation image but analysis not possible[/bold yellow]")
            print(f'{e!r}')
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

            dx = pole_center[0] - rotate_center[0]
            dy = pole_center[1] - rotate_center[1]

            pocs.say(f"dx: {dx:0.2f}")
            pocs.say(f"dy: {dy:0.2f}")

            fig = polar_alignment.plot_center(pole_fn, rotate_fn, pole_center, rotate_center)

            print(f"Plot image: {plot_fn}")
            fig.tight_layout()
            fig.savefig(plot_fn)

            latest_fn = images_dir / 'latest.jpg'
            if latest_fn.exists():
                latest_fn.unlink()

            latest_fn.symlink_to(plot_fn)

            with Path(images_dir / 'drift_align' / 'center.txt').open('a') as f:
                f.write(
                    f'{start_time},{pole_center[0]},{pole_center[1]},{rotate_center[0]},{rotate_center[1]},{dx},{dy}\n'
                )

            pocs.say("Done with polar alignment test")
    except KeyboardInterrupt:
        print('[red]POCS alignment interrupted by user, shutting down.[/red]')
    except PanError as e:
        print('[bold red]POCS encountered an error.[/bold red]')
        print(e)
    except Exception as e:
        print('[bold red]POCS encountered an error.[/bold red]')
        print(e)
    else:
        print('[green]POCS alignment finished, shutting down.[/green]')
    finally:
        print(f'[bold yellow]Please be patient, this may take a moment while the mount parks itself.[/bold yellow]')
        pocs.observatory.mount.park()

        pocs.power_down()


@app.command(name='quick-alignment')
def run_quick_alignment(
    context: typer.Context,
    exp_time: float = typer.Option(20.0, '--exptime', '-e', help='Exposure time in seconds.'),
    move_time: float = typer.Option(3.0, '--move-time', '-m', help='Time to move to each side of the axis.'),
):
    """
    Runs a quick alignment analysis.

    This function will take three exposures, one while at the "home" position,
    which is the celestial pole, and one on each side of the axis. It will then
    analyze the images to figure out the center of rotation for the mount.

    A plot will be created showing the celestial pole and the RA rotation axis as
    well as an arrow indicating the difference between the two, which corresponds
    to the offset of the mount from the celestial pole.
    """
    pocs = get_pocs(context)
    print(f'[bold yellow]Starting POCS in alignment mode.[/bold yellow]')

    # Create a dummy observation.
    observation = Observation(
        Field('QuickAlignment', position=SkyCoord.from_name('Polaris')),
        exptime=exp_time,
        min_nexp=1,
        exp_set_size=1
    )
    pocs.observatory.current_observation = observation
    mount = pocs.observatory.mount

    procs = list()

    def _start_processing():
        process_proc = Process(
            target=pocs.observatory.process_observation, kwargs=dict(
                plate_solve=True,
                compress_fits=False,
                record_observations=False,
                make_pretty_images=False,
                upload_image=False
            )
        )
        process_proc.start()
        procs.append(process_proc)

    try:
        mount.unpark()

        # At home position for celestial sphere.
        print('Performing polar rotation test to find celestial sphere.')
        mount.slew_to_home(blocking=True)
        print(f'At home position, taking {exp_time} sec exposure')
        pocs.observatory.take_observation(blocking=True)
        _start_processing()

        # Move to side.
        print(f'Moving to east for {move_time} sec')
        mount.move_direction(direction='east', seconds=move_time)
        print(f'At east position, taking {exp_time} sec exposure')
        pocs.observatory.take_observation(blocking=True)
        _start_processing()

        # Move back to home.
        print('Moving back to home')
        mount.slew_to_home(blocking=True)

        # Move to other side.
        print(f'Moving to west for {move_time} sec')
        mount.move_direction(direction='west', seconds=move_time)
        print(f'At west position, taking {exp_time} sec exposure')
        pocs.observatory.take_observation(blocking=True)
        _start_processing()

        # Move back to home.
        print('Moving back to home')
        mount.slew_to_home()
    except Exception as e:
        print(f'[red]Error during alignment process: {e}[/red]')
        print('Error during alignment process, shutting down.')
        print('Parking mount')
        mount.park()
        return

    # Wait for all the processing to finish.
    print('Waiting for image processing to finish.')
    for proc in procs:
        proc.join()

    # Gather a list of files from the exposure_list.
    fits_files = defaultdict(dict)
    # Each camera should have three exposures: home, east, west
    for cam_id, exposures in pocs.observatory.current_observation.exposure_list.items():
        for position, exposure in zip(['home', 'east', 'west'], exposures):
            fits_files[cam_id][position] = exposure.path.with_suffix('.fits').as_posix()

    # Get the results form the alignment analysis for each camera.
    now = current_time(flatten=True)
    for cam_id, files in fits_files.items():
        try:
            print(f'Analyzing camera {cam_id} exposures')
            results = process_quick_alignment(files, logger=pocs.logger)

            if results:
                print(f'Camera {cam_id} alignment results:')
                print(f"\tDelta (degrees): {results.dx_deg:.02f} {results.dy_deg:.02f}")

                # Plot.
                fig = plot_alignment_diff(cam_id, files, results)
                alignment_plot_fn = Path(observation.directory) / f'{cam_id}-{now}-alignment_overlay.jpg'
                fig.savefig(alignment_plot_fn.absolute().as_posix())
                print(f'\tPlot image: {alignment_plot_fn.absolute().as_posix()}')

                # Save deltas to CSV.
                csv_path = Path(observation.directory) / f'{cam_id}-{now}-alignment.csv'
                line = f'{now},{cam_id},{results.dx_deg:.02f},{results.dy_deg:.02f}'
                csv_path.write_text(line, encoding='utf-8', newline='\n')
        except Exception as e:
            print(f'[red]Error during alignment analysis for camera {cam_id}: {e}[/red]')
            continue

    print('Done with quick alignment test')
    print('[bold red]MOUNT IS STILL AT HOME POSITION[/bold red]')

    option, index = pick(
        ['Home', 'Park', 'Nothing'],
        'What would you like to do next?',
        clear_screen=False
    )
    if option == 'Home':
        print("[green]Moving mount to the home position (don't forget to park!)[/green]")
        mount.slew_to_home(blocking=True)
    elif option == 'Park':
        print('[green]Moving mount to the parking position [/green]')
        mount.home_and_park(blocking=True)


def polar_rotation(pocs: POCS, base_dir: Path | str, exp_time: Number = 30, **kwargs):
    assert base_dir is not None, print("base_dir cannot be empty")

    # Make sure base_dir is a Path and valid.
    base_dir = Path(base_dir)

    mount = pocs.observatory.mount

    print('Performing polar rotation test')
    pocs.say('Performing polar rotation test')
    mount.slew_to_home()

    while not mount.is_home:
        time.sleep(2)

    analyze_fn = None

    print(f'At home position, taking {exp_time} sec exposure')
    pocs.say(f'At home position, taking {exp_time} sec exposure')
    procs = dict()
    for cam_name, cam in pocs.observatory.cameras.items():
        if cam.is_primary:
            fn = base_dir / f'pole_{cam_name.lower()}.cr2'
            proc = cam.take_exposure(seconds=exp_time, filename=fn.as_posix(), blocking=True)
            procs[fn] = proc
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


def mount_rotation(pocs: POCS, base_dir: Path | str, include_west: bool = False, west_time: Number = 11,
                   east_time: Number = 21, **kwargs
                   ):
    mount = pocs.observatory.mount

    assert base_dir is not None, print("base_dir cannot be empty")
    base_dir = Path(base_dir)

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
            if cam.is_primary:
                fn = base_dir / f'rotation_{direction}_{cam_name.lower()}.cr2'
                proc = cam.take_exposure(seconds=exp_time, filename=fn.as_posix(), blocking=False)
                procs[fn] = proc
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
