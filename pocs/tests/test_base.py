import os
import time
import subprocess
import pytest

from pocs.base import PanBase
from pocs import hardware
from panoptes.utils.logger import get_root_logger
from panoptes.utils.config.client import set_config


# Override default config_server and use function scope so we can change some values cleanly.
@pytest.fixture(scope='function')
def config_server(config_port, images_dir, db_name):
    cmd = os.path.join(os.getenv('PANDIR'),
                       'panoptes-utils',
                       'scripts',
                       'run_config_server.py'
                       )
    args = [cmd, '--host', 'localhost', '--port', config_port, '--ignore-local', '--no-save']

    logger = get_root_logger()
    logger.debug(f'Starting config_server for testing function: {args!r}')

    proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    logger.critical(f'config_server started with PID={proc.pid}')

    # Give server time to start
    time.sleep(1)

    # Adjust various config items for testing
    unit_name = 'Generic PANOPTES Unit'
    unit_id = 'PAN000'
    logger.debug(f'Setting testing name and unit_id to {unit_id}')
    set_config('name', unit_name, port=config_port)
    set_config('pan_id', unit_id, port=config_port)

    logger.debug(f'Setting testing database to {db_name}')
    set_config('db.name', db_name, port=config_port)

    fields_file = 'simulator.yaml'
    logger.debug(f'Setting testing scheduler fields_file to {fields_file}')
    set_config('scheduler.fields_file', fields_file, port=config_port)

    # TODO(wtgee): determine if we need separate directories for each module.
    logger.debug(f'Setting temporary image directory for testing')
    set_config('directories.images', images_dir, port=config_port)

    # Make everything a simulator
    set_config('simulator', hardware.get_simulator_names(simulator=['all']), port=config_port)

    yield
    logger.critical(f'Killing config_server started with PID={proc.pid}')
    proc.terminate()


def test_mount_in_config(config_server, config_port):
    set_config('mount', {}, port=config_port)
    with pytest.raises(SystemExit):
        PanBase(config_port=config_port)


def test_directories_in_config(config_server, config_port):
    set_config('directories', {}, port=config_port)
    with pytest.raises(SystemExit):
        PanBase(config_port=config_port)


def test_state_machine_in_config(config_server, config_port):
    set_config('state_machine', {}, port=config_port)
    with pytest.raises(SystemExit):
        PanBase(config_port=config_port)
