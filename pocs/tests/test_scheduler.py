import pytest
import time
from multiprocessing import Process

from panoptes.utils import error
from panoptes.utils.logger import get_root_logger
from panoptes.utils.config.client import set_config
from pocs.scheduler import create_scheduler_from_config
from pocs.utils.location import create_location_from_config
from pocs import hardware
from panoptes.utils.config.server import app


@pytest.fixture(scope='module')
def config_port():
    return '4861'


# Override default config_server and use function scope so we can change some values cleanly.
@pytest.fixture(scope='module')
def config_server(config_host, config_port, config_server_args, images_dir, db_name):

    logger = get_root_logger()
    logger.critical(f'Starting config_server for testing function')

    def start_config_server():
        # Load the config items into the app config.
        for k, v in config_server_args.items():
            app.config[k] = v

        # Start the actual flask server.
        app.run(host=config_host, port=config_port)

    proc = Process(target=start_config_server)
    proc.start()

    logger.info(f'config_server started with PID={proc.pid}')

    # Give server time to start
    time.sleep(1)

    # Adjust various config items for testing
    unit_name = 'Generic PANOPTES Unit'
    unit_id = 'PAN000'
    logger.info(f'Setting testing name and unit_id to {unit_id}')
    set_config('name', unit_name, port=config_port)
    set_config('pan_id', unit_id, port=config_port)

    logger.info(f'Setting testing database to {db_name}')
    set_config('db.name', db_name, port=config_port)

    fields_file = 'simulator.yaml'
    logger.info(f'Setting testing scheduler fields_file to {fields_file}')
    set_config('scheduler.fields_file', fields_file, port=config_port)

    # TODO(wtgee): determine if we need separate directories for each module.
    logger.info(f'Setting temporary image directory for testing')
    set_config('directories.images', images_dir, port=config_port)

    # Make everything a simulator
    set_config('simulator', hardware.get_simulator_names(simulator=['all']), port=config_port)

    yield
    logger.critical(f'Killing config_server started with PID={proc.pid}')
    proc.terminate()


def test_bad_scheduler_type(config_server, config_port):
    set_config('scheduler.type', 'foobar', port=config_port)
    site_details = create_location_from_config(config_port=config_port)
    with pytest.raises(error.NotFound):
        create_scheduler_from_config(observer=site_details['observer'], config_port=config_port)


def test_bad_scheduler_fields_file(config_server, config_port):
    set_config('scheduler.fields_file', 'foobar', port=config_port)
    site_details = create_location_from_config(config_port=config_port)
    with pytest.raises(error.NotFound):
        create_scheduler_from_config(observer=site_details['observer'], config_port=config_port)


def test_no_observer(config_server, config_port):
    assert create_scheduler_from_config(observer=None, config_port=config_port) is None


def test_no_scheduler_in_config(config_server, config_port):
    set_config('scheduler', None, port=config_port)
    site_details = create_location_from_config(config_port=config_port)
    assert create_scheduler_from_config(
        observer=site_details['observer'], config_port=config_port) is None
