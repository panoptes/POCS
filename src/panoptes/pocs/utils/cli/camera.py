from pathlib import Path
from time import sleep

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
):
    """Takes pictures with cameras.

    """
    print('Taking pictures')
    cameras = create_cameras_from_config()

    # For a unique filename.
    now = current_time(flatten=True)
    output_dir = Path(output_dir) / str(now)

    for i in range(num_images):
        threads = list()
        for cam_name, cam in cameras.items():
            fn = output_dir / f'{cam_name}-{i:04d}.cr2'
            thread = cam.take_exposure(seconds=exptime, filename=fn, blocking=False)
            threads.append(thread)

        # Wait for cameras to finish.
        for thread in threads:
            thread.join()
