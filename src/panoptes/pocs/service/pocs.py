import threading

from fastapi import FastAPI

from panoptes.pocs.core import POCS
from panoptes.pocs.observatory import Observatory
from panoptes.pocs.camera import create_cameras_from_config
from panoptes.pocs.mount import create_mount_from_config
from panoptes.pocs.scheduler import create_scheduler_from_config

app = FastAPI()

pocs: POCS
run_proc: threading.Thread


@app.on_event('startup')
async def setup_pocs():
    # Long-lived pocs object
    mount = create_mount_from_config()
    scheduler = create_scheduler_from_config()
    cameras = create_cameras_from_config()

    observatory = Observatory(mount=mount, scheduler=scheduler, cameras=cameras)

    global pocs
    global run_proc
    pocs = POCS(observatory=observatory)
    run_proc = threading.Thread(target=pocs.run, daemon=True)
    print(f'POCS process started on {run_proc!r}')


@app.on_event('shutdown')
async def shutdown_pocs():
    pocs.power_down()


def get_status():
    status = pocs.status
    status['is_thread_running'] = run_proc.is_alive()
    return f'Status {status}'


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
