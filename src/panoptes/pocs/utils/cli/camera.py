from pathlib import Path
import time
import typer
from panoptes.utils.time import current_time
from rich import print

from panoptes.pocs.camera import create_cameras_from_config

app = typer.Typer()


@app.command(name='take-pics')
def take_pictures(
        num_images: int = 1,
        exptime: float = 1.0,
        output_dir: Path = '/home/panoptes/images',
        delay: float = 0.0,
):
    """Takes pictures with cameras.

    """
    cameras = create_cameras_from_config()
    if len(cameras) == 0:
        print('No cameras found, exiting.')
        return

    print(f'Taking {num_images} images with {len(cameras)} cameras.')

    # For a unique filename.
    now = current_time(flatten=True)
    output_dir = Path(output_dir) / str(now)

    for i in range(num_images):
        print(f'Taking image {i + 1} of {num_images}')
        threads = list()
        for cam_name, cam in cameras.items():
            fn = output_dir / f'{cam_name}-{i:04d}-{current_time(flatten=True)}.{cam.file_extension}'
            thread = cam.take_exposure(seconds=exptime, filename=fn, blocking=False)
            threads.append(thread)

        # Wait for cameras to finish.
        for thread in threads:
            thread.join()

        # Wait for delay.
        print(f'Waiting {delay} seconds')
        time.sleep(delay)
