#!/usr/bin/env python3

import os
import subprocess
import threading
import time
from collections import deque
from pathlib import Path
from threading import Thread

from google.cloud import storage
from panoptes.utils.config.client import get_config
from panoptes.utils.images import make_pretty_image
from panoptes.utils.serializers import from_yaml
from panoptes.utils.time import current_time, flatten_time
from rich import print

from panoptes.pocs.camera import create_cameras_from_config
from panoptes.pocs.utils.cloud import upload_image

VERSION = '2025-03-12'

################################################################
# CHANGELOG
#
# 2025-03-12    wtg     * Updates to match new project. Slightly more generic
#                           file structure.
# 2021-05-20    wtg     * Changed version number to be a date.
#                       * Script only handles taking images and does not
#                           control the mount.
# 0.0.6         wtg     * Changed order of cropping fits file. (WIP)
#                       * Continue on upload_blob fail.
#
################################################################

PROJECT_ID = os.getenv('PROJECT_ID', 'panoptes-project-01')
BUCKET_NAME = os.getenv('BUCKET_NAME', 'panoptes-special-events')
OUTPUT_BUCKET_NAME = os.getenv('BUCKET_NAME', 'panoptes-special-events')
OUTPUT_DIRECTORY = Path('/home/panoptes/images/')
SETTINGS_FILE = Path('/home/panoptes/POCS/resources/scripts/eclipse/lunar-exposure-times.yaml')

try:
    storage_client = storage.Client(project=PROJECT_ID)
except RuntimeError:
    print(f"Can't load Google credentials, won't be able to upload")
    storage_client = None

stop_event = threading.Event()

upload_queue = deque(maxlen=25)


def main(*args, **kwargs):
    unit_id = get_config('pan_id', '').upper()
    output_dir = OUTPUT_DIRECTORY / unit_id
    output_dir.mkdir(exist_ok=True)

    cameras = create_cameras_from_config()

    if not cameras:
        print(f'No cameras found, exiting')
        return

    # Load exposure settings
    exptimes = list()
    with SETTINGS_FILE.open() as f:
        exposure_settings = from_yaml(f.read())
        for setting in exposure_settings['settings']:
            exptimes.append(setting['exptime'])

    print("[bold yellow]🌑  🌒  🌓  🌔  🌕   Starting POCS for Moon shots  🌕  🌖  🌗  🌘  🌑[/bold yellow]")
    print(f"[bold yellow]Using exposure times: {exptimes}[/bold yellow]")

    try:
        start_pictures(
            cameras,
            exposure_settings['settings'],
            output_dir,
            unit_id=unit_id,
        )
    except KeyboardInterrupt:
        print('Stopping script, please wait for current image to finish.')
        stop_event.set()
        for t in upload_queue:
            t.join()
    except Exception as e:
        print(f'Error in pictures: {e!r}')


def start_pictures(cameras, exposure_settings, output_dir, unit_id=None, upload=True):
    while not stop_event.is_set():
        # Loop through exposure settings.
        for settings in exposure_settings:
            shutter_index = settings['shutter_index']
            exptime = settings['exptime']
            iso = settings['iso']

            cr2_files = take_pics(cameras, output_dir, settings=settings, unit_id=unit_id)

            if upload:
                for cr2_fn in cr2_files:
                    t = Thread(target=upload_blob, args=(cr2_fn, ))
                    t.start()
                    upload_queue.append(t)


def take_pics(cameras, obs_dir, settings, unit_id=None, cr2_fn='LunarEclipse/{}-{}-{}-{}.cr2'):
    """ Loops over the cameras, sets filename, waits for events, waits for files."""
    events = list()
    fns = list()
    image_time = current_time()
    exptime = str(settings['exptime']).replace('/', '_')
    for cam_name, cam in cameras.items():
        # Setup filename.
        fn = obs_dir / cr2_fn.format(unit_id, cam_name.upper(), exptime, flatten_time(image_time))
        print(f'Taking {exptime} second image on {fn}')
        fns.append(fn)

        exposure_event = take_pic(cam.port, fn, settings)
        events.append(exposure_event)

    # Wait for exposures to finish.
    while True:
        if all([e.poll() == 0 for e in events]):
            break
        time.sleep(1)

    # Wait for file to appear on hard drive.
    max_wait = 10
    t0 = time.perf_counter()
    while not all([os.path.exists(f) for f in fns]):
        print(f'Waiting for files to exist: {fns!r}')
        time.sleep(1)
        t1 = time.perf_counter()
        if t1 - t0 > max_wait:
            break

    return fns


def take_pic(port, cr2_fn, settings):
    # Get settings.
    shutter_index = str(settings['shutter_index'])
    exptime = str(settings['exptime'])
    iso = str(settings['iso'])

    base_script_path = Path(os.getenv('PANDIR', '/')) / 'resources/scripts/eclipse/'

    # If shutter_index is zero (bulb), use regular script, otherwise the bias.
    if shutter_index == "0":
        script_path = base_script_path / 'take-pic.sh'
        cmd = [str(script_path), port, exptime, str(cr2_fn), iso]
    else:
        script_path = base_script_path / 'take-bias.sh'
        cmd = [str(script_path), port, str(cr2_fn), shutter_index, iso]

    p = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    return p


def upload_blob(image_path, jpg_local_path):
    """Uploads a file to the bucket."""
    try:
        jpg_fn = make_pretty_image(image_path)

        images_dir = (Path('/home/panoptes/images/').expanduser().as_posix())
        bucket_path = Path(image_path.as_posix()[image_path.as_posix().find(images_dir) + len(images_dir):])

        # print(f'Uploading {image_path} to {bucket_path}')

        # Upload CR2.
        public_url = upload_image(
            file_path=image_path,
            bucket_path=bucket_path.as_posix(),
            bucket_name=OUTPUT_BUCKET_NAME,
        )

        # print(f'Public url: {public_url}')

        pretty_image_url = upload_image(
            file_path=jpg_local_path,
            bucket_path=bucket_path.with_suffix(".jpg").as_posix().replace(".cr2", ""),
            bucket_name=OUTPUT_BUCKET_NAME,
        )
        print(f'Pretty image url: {pretty_image_url}')
    except Exception as e:
        print(f'Upload fail: {e!r}')
        return None

    return None


if __name__ == '__main__':
    main()
