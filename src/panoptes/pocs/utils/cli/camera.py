import concurrent.futures
import queue
import threading
import time
from collections import defaultdict
from pathlib import Path
from platform import uname
from typing import Dict, List

import typer
from panoptes.utils.config.client import get_config, set_config
from panoptes.utils.error import PanError

# Import panoptes-utils image processing
from panoptes.utils.images import cr2 as cr2_utils, make_pretty_image
from panoptes.utils.images.fits import fpack, get_solve_field
from panoptes.utils.time import current_time
from rich import print
from rich.columns import Columns
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)

from panoptes.pocs.camera import (
    AbstractCamera,
    create_cameras_from_config,
    list_connected_gphoto2_cameras,
)
from panoptes.pocs.camera.libasi import ASIDriver

app = typer.Typer()


@app.command(name="setup")
def setup_cameras(
    detect_dslr: bool = True,
    detect_zwo: bool = True,
    asi_library_path: Path = None,
) -> None:
    """Set up the config for the cameras.

    1. Try to detect DSLRs via gphoto2.
    2. Try to detect ZWOs via ZWO SDK.
        a). Look for filterwheel.
    3. Update config options for camera.
    4. Update camera with any initialization settings.
    5. Take a test picture with each camera.

    """
    cameras = dict()
    num_cameras = 0
    if detect_dslr:
        print("Detecting DSLRs...")
        gphoto2_ports = list_connected_gphoto2_cameras()
        if gphoto2_ports:
            print(f"Detected {len(gphoto2_ports)} DSLR cameras.")
            for i, port in enumerate(gphoto2_ports):
                cameras[f"dslr-{i:02d}"] = {
                    "model": "panoptes.pocs.camera.gphoto.canon.Camera",
                    "name": f"Cam{num_cameras:02d}",
                    "port": port,
                    "readout_time": 15.0,
                }
                num_cameras += 1

    if detect_zwo:
        print("Detecting ZWO cameras...")
        if asi_library_path is None:
            platform = uname().machine
            if platform == "x86_64":
                platform = "x64"
            elif platform == "aarch64":
                platform = "armv8"
            asi_library_path = (
                Path(get_config("directories.base"))
                / f"resources/cameras/zwo/{platform}/libASICamera2.so.1.38"
            )
        # print(f'Using ZWO library path: {asi_library_path}')
        asi_driver = ASIDriver(library_path=asi_library_path)
        try:
            zwo_cameras = asi_driver.get_devices()
        except PanError:
            print("No ZWO cameras detected")
        else:
            print(f"Detected {len(zwo_cameras)} ZWO cameras.")
            for i, (serial_number, cam_id) in enumerate(zwo_cameras.items()):
                cameras[f"zwo-{i:02d}"] = {
                    "model": "panoptes.pocs.camera.zwo.Camera",
                    "name": f"Cam{num_cameras:02d}",
                    "serial_number": serial_number,
                    "file_extension": "fits",
                    "readout_time": 1.0,
                    "uid": serial_number,
                    "library_path": asi_library_path.absolute().as_posix(),
                }
                num_cameras += 1
                # Close the camera by id.
                asi_driver.close_camera(cam_id)

    if not cameras:
        print("No cameras detected, exiting.")
        return

    print(f"Found {num_cameras} cameras to set up.")
    print("Updating camera config...")
    set_config("cameras.devices", list(cameras.values()))

    # Turn off the autodetect
    set_config("cameras.defaults.auto_detect", False)

    # Now create the cameras from the config, calling the `setup_camera` method if available.
    print("Now creating the cameras from the config and setting them up.")
    cameras = create_cameras_from_config()
    if len(cameras) == 0:
        print("No cameras found after setup, exiting.")
        return
    else:
        # Call setup_properties on each of the cameras
        for cam_name, cam in cameras.items():
            try:
                print(f"Setting up camera: {cam_name}")
                cam.setup_camera()
            except AttributeError:
                print(f"Camera {cam_name} does not have a setup_camera method, skipping.")

    print("Now creating the cameras from the config and taking a test picture with each.")
    take_pictures(num_images=1, exptime=1.0, output_dir="/home/panoptes/images/test")


@app.command(name="take-pics")
def take_pictures(
    num_images: int = 1,
    exptime: float = 1.0,
    output_dir: str = "/home/panoptes/images",
    delay: float = 0.0,
    convert: bool = typer.Option(False, help="Convert to FITS if needed."),
    compress: bool = typer.Option(False, help="Compress FITS to .fz."),
    solve: bool = typer.Option(False, help="Solve FITS with astrometry."),
    pretty: bool = typer.Option(False, help="Create pretty PNG image."),
    verbose: bool = typer.Option(False, help="Print detailed processing output."),
) -> Dict[str, List[Path]] | None:
    """Takes pictures with cameras and optionally processes them."""
    cameras = create_cameras_from_config()
    if len(cameras) == 0:
        print("No cameras found, exiting.")
        return None

    print(f"Taking {num_images} images with {len(cameras)} cameras.")

    now = current_time(flatten=True)
    output_dir = Path(output_dir) / str(now)

    # Build per-camera progress panels
    per_cam_progress = {}
    panels = []
    for cam_name in cameras.keys():
        prog = Progress(
            TextColumn("[progress.description]{task.description}"),
            SpinnerColumn(),
            BarColumn(),
            TaskProgressColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
        )
        tasks: dict[str, int] = {"expose": prog.add_task("Expose", total=num_images)}
        # Conditionally add processing tasks
        if convert:
            tasks["convert"] = prog.add_task("Convert", total=num_images)
        if compress:
            tasks["compress"] = prog.add_task("Compress", total=num_images)
        if solve:
            tasks["solve"] = prog.add_task("Solve", total=num_images)
        if pretty:
            tasks["pretty"] = prog.add_task("Pretty", total=num_images)

        per_cam_progress[cam_name] = {"progress": prog, "tasks": tasks}
        panels.append(Panel(prog, title=f"{cam_name}", border_style="cyan"))

    # Set up queues and processing thread. Pass per-camera progress so it can update from the worker thread.
    process_queue = queue.Queue()
    complete_queue = queue.Queue()
    t = threading.Thread(
        target=process_image,
        args=(
            process_queue,
            complete_queue,
            convert,
            compress,
            solve,
            pretty,
            verbose,
            per_cam_progress,
        ),
        daemon=True,
    )
    t.start()

    layout = Columns(panels)

    # Submit all the images for exposure and render live progress while running.
    futures = dict()
    with Live(layout, refresh_per_second=10, transient=False):
        with concurrent.futures.ThreadPoolExecutor() as executor:
            for cam_name, cam in cameras.items():
                future = executor.submit(
                    _take_pics,
                    cam_name,
                    cam,
                    process_queue,
                    exptime,
                    num_images,
                    output_dir,
                    delay,
                    per_cam_progress[cam_name]["progress"],
                    per_cam_progress[cam_name]["tasks"]["expose"],
                )
                futures[future] = cam_name

            # Wait for all camera exposure jobs to complete
            for future in concurrent.futures.as_completed(futures):
                if future.exception():
                    print(future.exception())
                    continue

        # At this point, all exposure jobs are done. Wait for processing to finish.
        print("Finished taking pictures, waiting for processing.")

        # Signal processing thread to finish and wait for all processing.
        process_queue.put(None)
        process_queue.join()
        t.join()

    # Get the complete files.
    files = defaultdict(list)
    while not complete_queue.empty():
        cam_name, file = complete_queue.get()
        files[cam_name].append(file)

    # Print the files for each camera.
    for cam_name, file_list in files.items():
        print(f"Camera {cam_name} took pictures:")
        for file in file_list:
            print(f"  - {file}")

    return files


def _take_pics(
    cam_name: str,
    cam: AbstractCamera,
    process_queue: queue.Queue,
    exptime: float,
    num: int,
    output_dir: Path,
    delay: float,
    progress: Progress | None = None,
    expose_task_id: int | None = None,
):
    """Helper function to take pictures."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Take the images
    for i in range(num):
        fn = output_dir / f"{cam_name}-{i:04d}-{current_time(flatten=True)}.{cam.file_extension}"
        cam.take_exposure(seconds=exptime, filename=fn, blocking=True)
        process_queue.put((cam_name, fn))

        # Update per-camera exposure progress if provided
        if progress is not None and expose_task_id is not None:
            try:
                progress.update(expose_task_id, advance=1)
            except Exception:
                pass

        # Wait for delay.
        if delay and delay > 0.0:
            print(f"Waiting {delay} seconds on {cam_name}")
            time.sleep(delay)

    return None


def process_image(
    process_queue: queue.Queue,
    complete_queue: queue.Queue,
    convert_flag: bool,
    compress_flag: bool,
    solve_flag: bool,
    pretty_flag: bool,
    verbose_flag: bool,
    per_cam_progress: dict,
):
    """Process all the images that come into the queue until we receive a `None`."""
    while True:
        item = process_queue.get()
        if item is None:
            print("No pictures received, exiting.")
            process_queue.task_done()
            break

        cam_name, file_path = item
        cam_prog_entry = per_cam_progress.get(cam_name)
        cam_progress: Progress | None = None
        cam_tasks: dict | None = None
        if cam_prog_entry:
            cam_progress = cam_prog_entry.get("progress")
            cam_tasks = cam_prog_entry.get("tasks")

        # Convert to FITS if needed (e.g., from CR2)
        if convert_flag:
            try:
                if not file_path.suffix == ".fits":
                    file_path = cr2_utils.cr2_to_fits(file_path, remove_cr2=True)
                    if verbose_flag:
                        print(f"Converted {file_path} to FITS")
            except Exception as e:
                if verbose_flag:
                    print(f"Couldn't convert image to FITS: {e}")
                # If conversion failed, skip compression afterwards for this image
                compress_flag = False
            finally:
                # Advance convert task if present
                if cam_progress is not None and cam_tasks and "convert" in cam_tasks:
                    try:
                        cam_progress.update(cam_tasks["convert"], advance=1)
                    except Exception:
                        pass

        # Compress FITS to .fz
        if compress_flag:
            try:
                if file_path.suffix == ".fits":
                    file_path = Path(fpack(file_path.as_posix()))
                    if verbose_flag:
                        print(f"Compressed FITS to {file_path}")
            except Exception as e:
                if verbose_flag:
                    print(f"Couldn't compress {file_path}: {e}")
            finally:
                if cam_progress is not None and cam_tasks and "compress" in cam_tasks:
                    try:
                        cam_progress.update(cam_tasks["compress"], advance=1)
                    except Exception:
                        pass

        # Solve FITS
        if solve_flag:
            try:
                if file_path.suffix in (".fits", ".fz"):
                    get_solve_field(file_path)
                    if verbose_flag:
                        print(f"Solved {file_path}")
            except Exception as e:
                if verbose_flag:
                    print(f"Could not solve {file_path}: {e}")
            finally:
                if cam_progress is not None and cam_tasks and "solve" in cam_tasks:
                    try:
                        cam_progress.update(cam_tasks["solve"], advance=1)
                    except Exception:
                        pass

        # Make pretty image
        if pretty_flag:
            try:
                file_path = make_pretty_image(file_path.as_posix())
                if verbose_flag:
                    print(f"Created pretty image: {file_path}")
            except Exception as e:
                if verbose_flag:
                    print(f"Could not create pretty image for {file_path}: {e}")
            finally:
                if cam_progress is not None and cam_tasks and "pretty" in cam_tasks:
                    try:
                        cam_progress.update(cam_tasks["pretty"], advance=1)
                    except Exception:
                        pass

        complete_queue.put((cam_name, file_path))

        process_queue.task_done()
