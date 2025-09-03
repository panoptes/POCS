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
from panoptes.utils.serializers import from_yaml
from panoptes.utils.time import current_time, flatten_time

from panoptes.pocs.camera import create_cameras_from_config

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
SETTINGS_FILE = Path('lunar-exposure-times.yaml')

try:
    storage_client = storage.Client(project=PROJECT_ID)
except RuntimeError:
    print(f"Can't load Google credentials, won't be able to upload")
    storage_client = None


stop_event = threading.Event()


def main(*args, **kwargs):
    unit_id = get_config('pan_id', '').upper()
    output_dir = OUTPUT_DIRECTORY / unit_id
    output_dir.mkdir(exist_ok=True)

    upload = kwargs.get('upload', False)

    print(f'Initializing cameras')
    cameras = create_cameras_from_config()

    if not cameras:
        print(f'No cameras found, exiting')
        return

    # Load exposure settings
    with SETTINGS_FILE.open() as f:
        exposure_settings = from_yaml(f.read())
        print(f'Exposure settings: {exposure_settings!r}')

    try:
        start_pictures(
            cameras,
            exposure_settings['settings'],
            output_dir,
            unit_id=unit_id,
            upload=upload,
        )
    except KeyboardInterrupt:
        stop_event.set()
        print('Stopping script, please wait for current image to finish.')
    except Exception as e:
        print(f'Error in pictures: {e!r}')


def start_pictures(cameras, exposure_settings, output_dir, unit_id=None, upload=True):
    thread_deque = deque(maxlen=25)
    try:
        while not stop_event.is_set():
            # Loop through exposure settings.
            for settings in exposure_settings:
                shutter_index = settings['shutter_index']
                exptime = settings['exptime']
                iso = settings['iso']

                print(f'Image settings: {shutter_index=} {exptime=} {iso=}')
                cr2_files = take_pics(cameras, output_dir, settings=settings, unit_id=unit_id)

                if upload:
                    print(f'Processing files')
                    for cr2_fn in cr2_files:
                        t = Thread(target=upload_blob, args=(cr2_fn,))
                        t.start()
                        thread_deque.append(t)
    except KeyboardInterrupt:
        print(f'Cancelling images')


def take_pics(cameras, obs_dir, settings, unit_id=None, cr2_fn='LunarEclipse/{}-{}-{}-{}.cr2'):
    """ Loops over the cameras, sets filename, waits for events, waits for files."""
    events = list()
    fns = list()
    image_time = current_time()
    exptime = str(settings['exptime']).replace('/', '_')
    for cam_name, cam in cameras.items():
        # Setup filename.
        fn = obs_dir / cr2_fn.format(unit_id, cam_name.upper(), exptime, flatten_time(image_time))
        print(f'Taking image on {fn}')
        fns.append(fn)

        exposure_event = take_pic(cam.port, fn, settings)
        events.append(exposure_event)

    # Wait for exposures to finish.
    while True:
        if all([e.poll() == 0 for e in events]):
            break
        time.sleep(1)

    # Wait for file to appear on hard drive.
    while not all([os.path.exists(f) for f in fns]):
        print(f'Waiting for files to exist: {fns!r}')
        time.sleep(1)

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


def upload_blob(local_path, bucket_path=None):
    """Uploads a file to the bucket."""
    try:
        bucket_name = OUTPUT_BUCKET_NAME
        if storage_client is None:
            return None

        if bucket_path is None:
            bucket_path = 'LunarEclipse/' + os.path.basename(local_path)

        bucket = storage_client.get_bucket(bucket_name)

        # Create blob object
        blob = bucket.blob(bucket_path)

        # Upload file to blob
        blob.upload_from_filename(local_path)

        bucket_uri = f'https://storage.googleapis.com/{bucket_name}/{bucket_path}'
        print(f'Uploaded: {bucket_uri}')
    except Exception as e:
        print(f'Upload fail: {e!r}')
        return None

    return bucket_uri


if __name__ == '__main__':
    main()
