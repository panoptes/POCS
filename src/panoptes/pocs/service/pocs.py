import threading
from dataclasses import dataclass
from typing import Optional, Dict

from fastapi import FastAPI
from panoptes.pocs.core import POCS
from panoptes.pocs.mount import create_mount_from_config, create_mount_simulator
from panoptes.pocs.observatory import Observatory
from panoptes.pocs.utils.logger import get_logger
from panoptes.pocs import hardware


@dataclass
class State:
    pocs: POCS
    run_proc: threading.Thread
    verbose: bool = False


@dataclass
class Hardware:
    hardware: hardware.HardwareName
    simulator: bool = False


app = FastAPI()
state: Dict[str, Optional[State]] = {'metadata': None}
logger = get_logger(stderr_log_level='ERROR')


def get_status():
    metadata = state['metadata']
    if metadata.pocs:
        status = metadata.pocs.status
        status['is_thread_running'] = metadata.run_proc.is_alive()
        return status


@app.on_event('startup')
async def setup_pocs():
    observatory = Observatory()

    pocs = POCS(observatory=observatory)
    run_proc = threading.Thread(target=pocs.run, daemon=True)
    metadata = state['metadata']
    metadata['pocs'] = pocs
    metadata['run_proc'] = run_proc
    print(f'POCS process started: {metadata}')


@app.on_event('shutdown')
async def shutdown_pocs():
    metadata = state['metadata']
    metadata.pocs.power_down()


@app.get('/')
async def root():
    return get_status()


@app.get('/ping')
async def ping():
    return 'pong'


@app.post('/setup')
async def setup_hardware(
        new_hardware: Hardware,
):
    metadata = state['metadata']
    if new_hardware.hardware == hardware.HardwareName.mount:
        if new_hardware.simulator is False:
            mount = create_mount_from_config()
        else:
            mount = create_mount_simulator()
        logger.success(f'Adding {mount}')
        metadata.pocs.observatory.mount = mount

    return dict(got=new_hardware)


@app.get('/initialize')
async def initialize():
    metadata = state['metadata']
    metadata.pocs.initialize()
    return get_status()


@app.get('/run')
async def run():
    metadata = state['metadata']
    metadata.run_proc.start()
    return metadata.run_proc.is_alive()


@app.get('/stop-states')
async def stop_states():
    metadata = state['metadata']
    metadata.pocs.do_states = False
    metadata.run_proc.join(timeout=60)
    return metadata.run_proc.is_alive()
