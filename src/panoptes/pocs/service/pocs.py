import threading
from typing import Optional, List

from fastapi import FastAPI
from panoptes.pocs.camera import create_cameras_from_config

from panoptes.pocs.core import POCS
from panoptes.pocs.mount import create_mount_from_config
from panoptes.pocs.observatory import Observatory
from panoptes.pocs.scheduler import create_scheduler_from_config
from panoptes.utils.serializers import to_json, from_json

app = FastAPI()

# Long-lived pocs object
observatory = Observatory()
pocs: POCS = POCS(observatory=observatory)
run_proc: threading.Thread = threading.Thread(target=pocs.run, daemon=True)


def get_status():
    return f'Status {pocs.status}'


@app.get('/')
async def root():
    return get_status()


@app.get('/initialize')
async def initialize():
    pocs.initialize()
    return get_status()


@app.get('/run')
async def run():
    run_proc.start()
    return run_proc.is_alive()


@app.get('/stop-states')
async def stop_states():
    pocs.do_states = False
    run_proc.join(timeout=60)
    return run_proc.is_alive()


@app.get('/setup-hardware')
def setup_hardware():
    cameras = create_cameras_from_config()
    for cam_name, camera in cameras.items():
        pocs.observatory.add_camera(cam_name, camera)
    pocs.observatory.mount = create_mount_from_config()
    pocs.observatory.scheduler = create_scheduler_from_config()


@app.post('/add-simulator')
def add_simulator(simulator_name: str):
    simulator_lookup = {
        'mount': create_mount_from_config
    }

    try:
        simulator_lookup[simulator_name]()
    except:
        pocs.logger.warning("Can't create simulator.")
