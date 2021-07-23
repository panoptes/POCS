import shutil
import sys
import subprocess
from pathlib import Path
from typing import Optional, Dict, List
from threading import Lock
from datetime import datetime
from pydantic import BaseModel

from fastapi import FastAPI

from panoptes.pocs.camera import list_connected_cameras
from panoptes.pocs.camera.gphoto.canon import Camera

# Canon EOS models

iso_index_lookup = {
    100: 1,
    200: 2,
    400: 3,
    800: 4,
    1600: 5,
    3200: 6,
    6400: 7,
}

shutter_index_lookup = {
    30: 1,
    25: 2,
    20: 3,
    15: 4,
    13: 5,
    10.3: 6,
    8: 7,
    6.3: 8,
    5: 9,
    4: 10,
    3.2: 11,
    2.5: 12,
    2: 13,
    1.6: 14,
    1.3: 15,
    1: 16,
    0.8: 17,
    0.6: 18,
    0.5: 19,
    0.4: 20,
    0.3: 21,
    1 / 4: 22,
    1 / 5: 23,
    1 / 6: 24,
    1 / 8: 25,
    1 / 10: 26,
    1 / 13: 27,
    1 / 15: 28,
    1 / 20: 29,
    1 / 25: 30,
    1 / 30: 31,
    1 / 40: 32,
    1 / 50: 33,
    1 / 60: 34,
    1 / 80: 35,
    1 / 100: 36,
    1 / 125: 37,
    1 / 160: 38,
    1 / 200: 39,
    1 / 250: 40,
    1 / 320: 41,
    1 / 400: 42,
    1 / 500: 43,
    1 / 640: 44,
    1 / 800: 45,
    1 / 1000: 46,
    1 / 1250: 47,
    1 / 1600: 48,
    1 / 2000: 49,
    1 / 2500: 50,
    1 / 3200: 51,
    1 / 4000: 52,
}

eosremoterelease_index_lookup = {
    'None': 0,
    'Press Half': 1,
    'Press Full': 2,
    'Release Half': 3,
    'Release Full': 4,
    'Immediate': 5,
    'Press 1': 6,
    'Press 2': 7,
    'Press 3': 8,
    'Release 1': 9,
    'Release 2': 10,
    'Release 3': 11,
}


class Exposure(BaseModel):
    exptime: float
    filename: Optional[str] = None
    base_dir: Path = '.'
    iso: int = 100


app = FastAPI()
cameras: List[Camera] = []
locks: Dict[str, Lock] = {}


@app.on_event('startup')
def startup_tasks():
    gphoto2_path = shutil.which('gphoto2')
    if gphoto2_path is None:
        print('Cannot find gphoto2, exiting system.')
        sys.exit(1)

    initialize_cameras()


def initialize_cameras():
    """Look for attached cameras"""
    for i, port in enumerate(list_connected_cameras()):
        cameras.append(Camera(port=port, name=f'Cam{i:02d}', db_type='memory'))

    print(f'Found {cameras=!r}')


@app.post('/camera/{device_number}/startexposure')
def take_pic(device_number: int, exposure: Exposure):
    """Takes a picture with the camera."""
    camera = cameras[device_number]
    port_lock = locks.get(camera.port, Lock())
    if port_lock.locked():
        return {'message': f'Another exposure is currently in process for {camera.port=}',
                'success': False}

    with port_lock:
        # Look up shutter index based on requested exptime, otherwise `0` for bulb.
        shutter_index = shutter_index_lookup.get(exposure.exptime, 0)

        # Look up iso index, otherwise `1` for 100.
        iso_index = iso_index_lookup.get(exposure.iso, 1)

        commands = [
            f'--port={camera.port}',
            '--set-config-index', f'iso={iso_index}',
            '--set-config-index', f'shutterspeed={shutter_index}',
            '--wait-event=1s',  # gphoto2 needs this.
        ]

        # If using `bulb` shutter index we need to specify wait time, otherwise just capture.
        if shutter_index == 0:
            # Manually build bulb command.
            bulb_start_index = eosremoterelease_index_lookup['Press Full']
            bulb_stop_index = eosremoterelease_index_lookup['Release Full']

            commands.extend([
                '--set-config-index', f'eosremoterelease={bulb_start_index}',
                f'--wait-event={exposure.exptime}s',
                '--set-config-index', f'eosremoterelease={bulb_stop_index}',
                '--wait-event-and-download=1s'
            ])
        else:
            commands.extend(['--capture-image-and-download'])

        # Set up filename in the base_dir.
        filename = exposure.filename or datetime.now().strftime('%Y%m%dT%H%M%S')
        full_path = f'{exposure.base_dir}/{filename}.cr2'
        commands.extend([f'--filename={full_path}'])

        # Build the full command.
        full_command = [shutil.which('gphoto2'), *commands]

        completed_proc = gphoto2_command(full_command)

        # Return the full path upon success otherwise the output from command.
        if completed_proc.returncode:
            print(completed_proc.stdout)
            return {'success': False, 'message': completed_proc.stdout}
        else:
            print(f'Done taking picture {completed_proc.returncode}')
            return {'success': True, 'filename': full_path}


@app.get('/camera/{device_number}/shutterspeeds')
def get_shutterspeeds(device_number: int):
    return shutter_index_lookup


def gphoto2_command(command: List[str]) -> subprocess.CompletedProcess:
    """Run a gphoto2 command in a separate blocking process.

    Return a subprocess.CompletedProcess.
    """
    print(f'Running {command=}')

    # Run the blocking command in a separate process.
    completed_proc = subprocess.run(command, capture_output=True)

    return completed_proc
