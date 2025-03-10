import concurrent.futures
import time
from pathlib import Path
from typing import Dict, List

import typer
from panoptes.utils.time import current_time
from rich import print

from panoptes.pocs.camera import AbstractCamera, create_cameras_from_config

app = typer.Typer()


@app.command(name='take-pics')
def take_pictures(
    num_images: int = 1,
    exptime: float = 1.0,
    output_dir: Path = '/home/panoptes/images',
    delay: float = 0.0,
) -> Dict[str, List[Path]]:
    """Takes pictures with cameras.

    """
    cameras = create_cameras_from_config()
    if len(cameras) == 0:
        print('No cameras found, exiting.')
        return

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

