"""Typer-based CLI commands for running PANOPTES workflows.

Provides commands for automatic observing sessions and polar alignment helpers.
"""

import os
import warnings
from collections import defaultdict
from itertools import product
from multiprocessing import Process
from pathlib import Path

import typer
from astropy.coordinates import SkyCoord
from panoptes.utils.error import PanError
from panoptes.utils.time import current_time
from panoptes.utils.utils import altaz_to_radec, listify
from rich import print

from panoptes.pocs.core import POCS
from panoptes.pocs.scheduler.field import Field
from panoptes.pocs.scheduler.observation.base import Observation
from panoptes.pocs.utils.alignment import plot_alignment_diff, process_quick_alignment
from panoptes.pocs.utils.cloud import upload_image
from panoptes.pocs.utils.logger import get_logger

app = typer.Typer()

# Ignore FITS header warnings.
warnings.filterwarnings(action="ignore", message="datfix")


@app.callback()
def common(
    context: typer.Context,
    simulator: list[str] = typer.Option(None, "--simulator", "-s", help="Simulators to load"),
    cloud_logging: bool = typer.Option(False, "--cloud-logging", "-c", help="Enable cloud logging"),
):
    """Shared options for all commands.

    Args:
        context: Typer context object used to share state across commands.
        simulator: Optional list of simulators to load. Multiple values allowed.
        cloud_logging: If True, enables cloud logging at DEBUG level.
    """
    context.obj = [simulator, cloud_logging]


def get_pocs(context: typer.Context):
    """Helper to get POCS after confirming with user.

    Prompts the user for confirmation, prepares logging, constructs POCS from
    the config, initializes it, and returns the instance.

    Args:
        context: Typer context containing shared options from the callback.

    Returns:
        POCS: An initialized POCS instance ready to run.
    """
    simulators, cloud_logging = context.obj
    confirm = typer.prompt("Are you sure you want to run POCS automatically?", default="n")
    if confirm.lower() not in ["y", "yes"]:
        raise typer.Exit(0)

    # Change to home directory.
    os.chdir(os.path.expanduser("~"))

    simulators = listify(simulators)

    print(
        "[green]Running POCS automatically![/green]\n[bold green]Press Ctrl-c to quit.[/bold green]"
    )

    # If cloud logging is requested, set DEBUG level, otherwise the config
    # and regular set up will handle things.
    if cloud_logging:
        get_logger(cloud_logging_level="DEBUG")

    pocs = POCS.from_config(simulators=simulators)

    pocs.logger.debug("POCS created from config")
    pocs.logger.debug("Sending POCS config to cloud")
    try:
        pocs.db.insert_current("config", pocs.get_config())
    except Exception as e:
        pocs.logger.warning(f"Unable to send config to cloud: {e}")

    pocs.initialize()

    return pocs


@app.command(name="auto")
def run_auto(context: typer.Context) -> None:
    """Runs POCS automatically, like it's meant to be run.

    Args:
        context: Typer context carrying shared options.

    Returns:
        None
    """

    pocs = get_pocs(context)

    try:
        pocs.run()
    except KeyboardInterrupt:
        print("[red]POCS interrupted by user, shutting down.[/red]")
    except Exception as e:
        print("[bold red]POCS encountered an error.[/bold red]")
        print(e)
    else:
        print("[green]POCS finished, shutting down.[/green]")
    finally:
        print(
            "[bold yellow]Please be patient, this may take a moment while the mount parks itself.[/bold yellow]"
        )
        pocs.power_down()


@app.command(name="long-alignment")
def run_long_alignment(
    context: typer.Context,
    coords: list[str] = typer.Option(
        None, "--coords", "-c", help="Alt/Az coordinates to use, e.g. 40,120"
    ),
    exptime: float = typer.Option(30.0, "--exptime", "-e", help="Exposure time in seconds."),
    num_exposures: int = typer.Option(
        5, "--num-exposures", "-n", help="Number of exposures per coordinate."
    ),
    field_name: str = typer.Option("PolarAlignment", "--field-name", "-f", help="Name of field."),
) -> None:
    """Runs POCS in long alignment mode by sampling coordinates across the sky.

    If coordinates are not specified, defaults to a grid like:
        -c 55,60 -c 55,120 -c 55,240 -c 55,300
        -c 70,60 -c 70,120 -c 70,240 -c 70,300

    Args:
        context: Typer context carrying shared options.
        coords: List of "alt,az" strings or pairs used for alignment sampling. If None,
            a default grid is used.
        exptime: Exposure time in seconds for each image.
        num_exposures: Number of exposures to take at each coordinate.
        field_name: Name to use for the temporary alignment field.

    Returns:
        None
    """
    pocs = get_pocs(context)
    print("[bold yellow]Starting POCS in alignment mode.[/bold yellow]")
    pocs.update_status()

    alts = [55, 70]
    azs = [60, 120, 240, 300]

    altaz_coords = coords or list(product(alts, azs))
    altaz_coords = sorted(altaz_coords, key=lambda x: x[1])  # Sort by azimuth.
    print(f"Using {altaz_coords=} for alignment.\n")

    # Helper function to make an observation from altaz coordinates.
    def get_altaz_observation(coords, seq_time) -> Observation:
        alt, az = coords
        coord = altaz_to_radec(alt, az, pocs.observatory.earth_location, current_time())
        alignment_observation = Observation(
            Field(field_name, coord),
            exptime=exptime,
            min_nexp=num_exposures,
            exp_set_size=num_exposures,
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
                print("[red]POCS is not safe, shutting down.[/red]")
                raise PanError("POCS is not safe.")

            print(f"{field_name} #{i:02d}/{len(altaz_coords):02d} {altaz_coord=}")

            # Create an observation and set it as current.
            observation = get_altaz_observation(altaz_coord, sequence_time)
            pocs.observatory.current_observation = observation

            print(f"\tSlewing to RA/Dec {observation.field.coord.to_string()} for {altaz_coord=}")
            mount.unpark()
            target_set = mount.set_target_coordinates(observation.field.coord)

            # If the mount can't set the target coordinates, skip this observation.
            if not target_set:
                print(f"\tInvalid coords, skipping {altaz_coord=}")
                continue

            started_slew = mount.slew_to_target(blocking=True)

            # If the mount can't slew to the target, skip this observation.
            if not started_slew:
                print(f"\tNo slew, skipping {altaz_coord=}")
                continue

            # Take all the exposures for this altaz observation.
            for j in range(num_exposures):
                print(f"\tStarting {exptime}s exposure #{j + 1:02d}/{num_exposures:02d}")
                pocs.observatory.take_observation(blocking=True)
                pocs.update_status()

                # Do processing in background (if exposure time is long enough).
                if exptime > 10:
                    process_proc = Process(target=pocs.observatory.process_observation)
                    process_proc.start()
                    procs.append(process_proc)

            mount.query("stop_tracking")

    except KeyboardInterrupt:
        print("[red]POCS alignment interrupted by user, shutting down.[/red]")
    except Exception as e:
        print("[bold red]POCS encountered an error.[/bold red]")
        print(e)
    except PanError as e:
        print("[bold red]POCS encountered an error.[/bold red]")
        print(e)
    else:
        print("[green]POCS alignment finished, shutting down.[/green]")
    finally:
        print(
            "[bold yellow]Please be patient, this may take a moment while the mount parks itself.[/bold yellow]"
        )
        pocs.observatory.mount.park()

        # Wait for all the processing to finish.
        print("Waiting for image processing to finish.")
        for proc in procs:
            proc.join()

        pocs.power_down()


@app.command(name="alignment")
@app.command(name="quick-alignment")
def run_quick_alignment(
    context: typer.Context,
    exp_time: float = typer.Option(20.0, "--exptime", "-e", help="Exposure time in seconds."),
    move_time: float = typer.Option(
        3.0, "--move-time", "-m", help="Time to move to each side of the axis."
    ),
):
    """Run a quick alignment analysis using three exposures.

    This function will take three exposures, one while at the "home" position,
    which is the celestial pole, and one on each side of the axis. It will then
    analyze the images to figure out the center of rotation for the mount.

    A plot will be created showing the celestial pole and the RA rotation axis as
    well as an arrow indicating the difference between the two, which corresponds
    to the offset of the mount from the celestial pole.

    Args:
        context: Typer context carrying shared options.
        exp_time: Exposure time in seconds for each image.
        move_time: Time in seconds to move to each side of the RA axis before taking exposures.

    Returns:
        None
    """
    pocs = get_pocs(context)
    print("[bold yellow]Starting POCS in alignment mode.[/bold yellow]")

    # Create a dummy observation.
    observation = Observation(
        Field("QuickAlignment", position=SkyCoord.from_name("Polaris")),
        exptime=exp_time,
        min_nexp=1,
        exp_set_size=1,
    )
    pocs.observatory.current_observation = observation
    mount = pocs.observatory.mount

    procs = list()

    def _start_processing():
        process_proc = Process(
            target=pocs.observatory.process_observation,
            kwargs=dict(
                plate_solve=True,
                compress_fits=False,
                record_observations=False,
                make_pretty_images=False,
                upload_image=False,
            ),
        )
        process_proc.start()
        procs.append(process_proc)

    try:
        mount.unpark()

        # At home position for celestial sphere.
        print("Performing polar rotation test to find celestial sphere.")
        mount.slew_to_home(blocking=True)
        print(f"At home position, taking {exp_time} sec exposure")
        pocs.observatory.take_observation(blocking=True)
        _start_processing()

        # Move to side.
        print(f"Moving to east for {move_time} sec")
        mount.move_direction(direction="east", seconds=move_time)
        print(f"At east position, taking {exp_time} sec exposure")
        pocs.observatory.take_observation(blocking=True)
        _start_processing()

        # Move back to home.
        print("Moving back to home")
        mount.slew_to_home(blocking=True)

        # Move to other side.
        print(f"Moving to west for {move_time} sec")
        mount.move_direction(direction="west", seconds=move_time)
        print(f"At west position, taking {exp_time} sec exposure")
        pocs.observatory.take_observation(blocking=True)
        _start_processing()

        # Move back to home.
        print("Moving back to home")
        mount.slew_to_home()
    except Exception as e:
        print(f"[red]Error during alignment process: {e}[/red]")
        print("Error during alignment process, shutting down.")
        print("Parking mount")
        mount.park()
        return

    # Wait for all the processing to finish.
    print("Waiting for image processing to finish.")
    for proc in procs:
        proc.join()

    # Gather a list of files from the exposure_list.
    fits_files = defaultdict(dict)
    # Each camera should have three exposures: home, east, west
    for cam_id, exposures in pocs.observatory.current_observation.exposure_list.items():
        for position, exposure in zip(["home", "east", "west"], exposures):
            cam_uid = exposure.metadata["camera_uid"]
            fits_files[cam_uid][position] = exposure.path.with_suffix(".fits").as_posix()

    # Get the results form the alignment analysis for each camera.
    now = current_time(flatten=True)
    csv_path = Path(observation.directory) / "alignment.csv"
    csv_file = csv_path.open("a", encoding="utf-8")
    for cam_id, files in fits_files.items():
        try:
            print(f"Analyzing camera {cam_id} exposures")
            results = process_quick_alignment(files, logger=pocs.logger)

            if results:
                print(f"Camera {cam_id} alignment results:")
                print(
                    f"\tDelta (degrees): azimuth={results.az_deg:.02f} altitude={results.alt_deg:.02f}"
                )

                # Plot.
                fig = plot_alignment_diff(cam_id, files, results)
                alignment_plot_fn = (
                    Path(observation.directory) / f"{cam_id}-{now}-alignment_overlay.jpg"
                )
                fig.savefig(alignment_plot_fn.absolute().as_posix())
                print(f"\tPlot image: {alignment_plot_fn.absolute().as_posix()}")

                # Save deltas to CSV.
                csv_file.write(f"{now},{cam_id},{results.to_csv_line()}\n")

                # Remove everything in the path before 'images' for upload.
                path_parts = alignment_plot_fn.parts
                bucket_path = "/".join(path_parts[path_parts.index("images") + 1 :])
                upload_image(
                    file_path=alignment_plot_fn,
                    bucket_path=bucket_path,
                )
        except Exception as e:
            print(f"[red]Error during alignment analysis for camera {cam_id}: {e}[/red]")
            continue

    print("Done with quick alignment test")
    print("[bold red]MOUNT IS STILL AT HOME POSITION[/bold red]")
