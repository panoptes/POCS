import os
import time
import pytest
import subprocess

from pocs import hardware
from pocs.core import POCS
from pocs.observatory import Observatory
from panoptes.utils import error
from panoptes.utils.logger import get_root_logger
from panoptes.utils.config.client import set_config
from panoptes.utils.serializers import to_yaml


@pytest.fixture(scope='function')
def config_port():
    return '4861'


# Override default config_server and use function scope so we can change some values cleanly.
@pytest.fixture(scope='function')
def config_server(config_path, config_host, config_port, images_dir, db_name):
    cmd = os.path.join(os.getenv('PANDIR'),
                       'panoptes-utils',
                       'scripts',
                       'run_config_server.py'
                       )
    args = [cmd, '--config-file', config_path,
            '--host', config_host,
            '--port', config_port,
            '--ignore-local',
            '--no-save']

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


@pytest.fixture
def observatory(config_port):
    observatory = Observatory(simulator=['all'], config_port=config_port)

    yield observatory


def test_bad_state_machine_file():
    with pytest.raises(error.InvalidConfig):
        POCS.load_state_table(state_table_name='foo')


def test_load_bad_state(observatory, config_port):
    pocs = POCS(observatory, config_port=config_port)

    with pytest.raises(error.InvalidConfig):
        pocs._load_state('foo')


def test_state_machine_absolute(temp_file):
    state_table = POCS.load_state_table()
    assert isinstance(state_table, dict)

    with open(temp_file, 'w') as f:
        f.write(to_yaml(state_table))

    file_path = os.path.abspath(temp_file)
    assert POCS.load_state_table(state_table_name=file_path)
