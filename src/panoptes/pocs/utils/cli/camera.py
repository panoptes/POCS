import concurrent.futures
import time
from pathlib import Path
from typing import Dict, List

import typer
from panoptes.utils.config.client import get_config, set_config
from panoptes.utils.time import current_time
from rich import print

from panoptes.pocs.camera import AbstractCamera, create_cameras_from_config, list_connected_gphoto2_cameras
from panoptes.pocs.camera.libasi import ASIDriver

app = typer.Typer()


@app.command(name='setup')
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
        print('Detecting DSLRs...')
        gphoto2_ports = list_connected_gphoto2_cameras()
        if gphoto2_ports:
            print(f'Detected {len(gphoto2_ports)} DSLR cameras.')
            for i, port in enumerate(gphoto2_ports):
                cameras[f'dslr-{i:02d}'] = {
                    'model': 'panoptes.pocs.camera.gphoto.canon.Camera',
                    'name': f'Cam{num_cameras:02d}',
                    'port': port,
                    'readout_time': 5.0
                }
                num_cameras += 1

    if detect_zwo:
        print('Detecting ZWO cameras...')
        if asi_library_path is None:
            asi_library_path = Path(get_config('directories.resources')) / 'cameras/zwo/armv8/libASICamera2.so.1.37'
        print(f'Using ZWO library path: {asi_library_path}')
        asi_driver = ASIDriver(library_path=asi_library_path)
        zwo_cameras = asi_driver.get_devices()
        if zwo_cameras:
            print(f'Detected {len(zwo_cameras)} ZWO cameras.')
            for i, (serial_number, cam_id) in enumerate(zwo_cameras.items()):
                cameras[f'zwo-{i:02d}'] = {
                    'model': 'panoptes.pocs.camera.zwo.Camera',
                    'name': f'Cam{num_cameras:02d}',
                    'serial_number': serial_number,
                    'readout_time': 1.0,
                    'uid': cam_id,
                    'library_path': asi_library_path.absolute().as_posix(),
                }
                num_cameras += 1

    if not cameras:
        print('No cameras detected, exiting.')
        return

    print(f'Found {num_cameras} cameras to set up.')
    print('Updating camera config...')
    set_config('cameras.devices', list(cameras.values()))

    print('Now creating the cameras from the config and taking a test picture with each.')
    images = take_pictures(num_images=1, exptime=1.0, output_dir='/home/panoptes/images/test')


@app.command(name='take-pics')
def take_pictures(
    num_images: int = 1,
    exptime: float = 1.0,
    output_dir: str = '/home/panoptes/images',
    delay: float = 0.0,
) -> Dict[str, List[Path]] | None:
    """Takes pictures with cameras.

    """
    cameras = create_cameras_from_config()
    if len(cameras) == 0:
        print('No cameras found, exiting.')
        return None

    print(f'Taking {num_images} images with {len(cameras)} cameras.')

    now = current_time(flatten=True)
    output_dir = Path(output_dir) / str(now)

    futures = dict()
    with concurrent.futures.ThreadPoolExecutor() as executor:
        for cam_name, cam in cameras.items():
            future = executor.submit(_take_pics, cam_name, cam, exptime, num_images, output_dir, delay)
            futures[future] = cam_name

    for future in concurrent.futures.as_completed(futures):
        if future.exception():
            print(future.exception())
            continue

        print(f'{cam_name}: {future.result()}')

    return futures


def _take_pics(cam_name: str, cam: AbstractCamera, exptime: float, num: int, output_dir: Path, delay: float):
    files = list()
    for i in range(num):
        print(f'Taking {cam_name} image {i + 1} of {num}')
        fn = output_dir / f'{cam_name}-{i:04d}-{current_time(flatten=True)}.{cam.file_extension}'
        cam.take_exposure(seconds=exptime, filename=fn, blocking=True)
        files.append(fn)

        # Wait for delay.
        if delay and delay > 0.0:
            print(f'Waiting {delay} seconds on {cam_name}')
            time.sleep(delay)

    return files
