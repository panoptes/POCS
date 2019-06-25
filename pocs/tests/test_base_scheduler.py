import time
from multiprocessing import Process

import pytest
import yaml

from astropy import units as u
from astropy.coordinates import EarthLocation

from astroplan import Observer

from panoptes.utils import error
from panoptes.utils.logger import get_root_logger
from panoptes.utils.config.client import get_config
from panoptes.utils.config.client import set_config
from pocs import hardware
from pocs.scheduler import BaseScheduler as Scheduler
from pocs.scheduler.constraint import Duration
from pocs.scheduler.constraint import MoonAvoidance
from panoptes.utils.config.server import app


@pytest.fixture(scope='module')
def config_port():
    return '4861'


# Override default config_server and use function scope so we can change some values cleanly.
@pytest.fixture(scope='function')
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


@pytest.fixture
def constraints(config_server, config_port):
    return [MoonAvoidance(config_port=config_port), Duration(30 * u.deg, config_port=config_port)]


@pytest.fixture
def simple_fields_file(config_server, config_port):
    return get_config('directories.targets', port=config_port) + '/simulator.yaml'


@pytest.fixture
def observer(config_server, config_port):
    loc = get_config('location', port=config_port)
    location = EarthLocation(lon=loc['longitude'], lat=loc['latitude'], height=loc['elevation'])
    return Observer(location=location, name="Test Observer", timezone=loc['timezone'])


@pytest.fixture()
def field_list():
    return yaml.full_load("""
    -
        name: HD 189733
        position: 20h00m43.7135s +22d42m39.0645s
        priority: 100
    -
        name: HD 209458
        position: 22h03m10.7721s +18d53m03.543s
        priority: 100
    -
        name: Tres 3
        position: 17h52m07.02s +37d32m46.2012s
        priority: 100
        exp_set_size: 15
        min_nexp: 240
    -
        name: M5
        position: 15h18m33.2201s +02d04m51.7008s
        priority: 50
    -
        name: KIC 8462852
        position: 20h06m15.4536s +44d27m24.75s
        priority: 50
        exptime: 60
        exp_set_size: 15
        min_nexp: 45
    -
        name: Wasp 33
        position: 02h26m51.0582s +37d33m01.733s
        priority: 100
    -
        name: M42
        position: 05h35m17.2992s -05d23m27.996s
        priority: 25
        exptime: 240
    -
        name: M44
        position: 08h40m24s +19d40m00.12s
        priority: 50
    """)


@pytest.fixture
def scheduler(config_server, config_port, field_list, observer, constraints):
    return Scheduler(observer,
                     fields_list=field_list,
                     constraints=constraints,
                     config_port=config_port)


def test_scheduler_load_no_params(config_server, config_port):
    with pytest.raises(TypeError):
        Scheduler(config_port=config_port)


def test_no_observer(config_server, config_port, simple_fields_file):
    with pytest.raises(TypeError):
        Scheduler(fields_file=simple_fields_file, config_port=config_port)


def test_bad_observer(config_server, config_port, simple_fields_file, constraints):
    with pytest.raises(TypeError):
        Scheduler(fields_file=simple_fields_file,
                  constraints=constraints,
                  config_port=config_port)


def test_loading_target_file_check_file(config_server,
                                        config_port,
                                        observer,
                                        simple_fields_file,
                                        constraints):
    set_config('scheduler.check_file', False, port=config_port)
    scheduler = Scheduler(observer,
                          fields_file=simple_fields_file,
                          constraints=constraints,
                          config_port=config_port
                          )
    # Check the hidden property as the public one
    # will populate if not found.
    assert len(scheduler._observations)


def test_loading_target_file_no_check_file(config_server,
                                           config_port,
                                           observer,
                                           simple_fields_file,
                                           constraints):
    # If check_file is True then we will check the file
    # before each call to `get_observation`, but *not*
    # when the Scheduler is initialized.
    set_config('scheduler.check_file', True, port=config_port)
    scheduler = Scheduler(observer,
                          fields_file=simple_fields_file,
                          constraints=constraints,
                          config_port=config_port
                          )
    # Check the hidden property as the public one
    # will populate if not found.
    assert len(scheduler._observations) == 0


def test_loading_target_file_via_property(config_port, simple_fields_file, observer, constraints):
    scheduler = Scheduler(observer, fields_file=simple_fields_file,
                          constraints=constraints, config_port=config_port)
    scheduler._observations = dict()
    assert scheduler.observations is not None


def test_with_location(scheduler):
    assert isinstance(scheduler, Scheduler)


def test_loading_bad_target_file(config_port, observer):
    with pytest.raises(FileNotFoundError):
        Scheduler(observer, fields_file='/var/path/foo.bar', config_port=config_port)


def test_new_fields_file(scheduler, simple_fields_file):
    scheduler.fields_file = simple_fields_file
    assert scheduler.observations is not None


def test_new_fields_list(scheduler):
    assert len(scheduler.observations.keys()) > 2
    scheduler.fields_list = [
        {'name': 'Wasp 33',
         'position': '02h26m51.0582s +37d33m01.733s',
         'priority': '100',
         },
        {'name': 'Wasp 37',
         'position': '02h26m51.0582s +37d33m01.733s',
         'priority': '50',
         },
    ]
    assert scheduler.observations is not None
    assert len(scheduler.observations.keys()) == 2


def test_scheduler_add_field(scheduler):
    orig_length = len(scheduler.observations)

    scheduler.add_observation({
        'name': 'Degree Field',
        'position': '12h30m01s +08d08m08s',
    })

    assert len(scheduler.observations) == orig_length + 1


def test_scheduler_add_bad_field(scheduler):

    orig_length = len(scheduler.observations)
    with pytest.raises(error.InvalidObservation):
        scheduler.add_observation({
            'name': 'Duplicate Field',
            'position': '12h30m01s +08d08m08s',
            'exptime': -10
        })

    assert orig_length == len(scheduler.observations)


def test_scheduler_add_duplicate_field(scheduler):

    scheduler.add_observation({
        'name': 'Duplicate Field',
        'position': '12h30m01s +08d08m08s',
        'priority': 100
    })

    assert scheduler.observations['Duplicate Field'].priority == 100

    scheduler.add_observation({
        'name': 'Duplicate Field',
        'position': '12h30m01s +08d08m08s',
        'priority': 500
    })

    assert scheduler.observations['Duplicate Field'].priority == 500


def test_scheduler_add_duplicate_field_different_name(scheduler):
    orig_length = len(scheduler.observations)

    scheduler.add_observation({
        'name': 'Duplicate Field',
        'position': '12h30m01s +08d08m08s',
    })

    scheduler.add_observation({
        'name': 'Duplicate Field 2',
        'position': '12h30m01s +08d08m08s',
    })

    assert len(scheduler.observations) == orig_length + 2


def test_scheduler_add_with_exptime(scheduler):
    orig_length = len(scheduler.observations)

    scheduler.add_observation({
        'name': 'Added Field',
        'position': '12h30m01s +08d08m08s',
        'exptime': '60'
    })

    assert len(scheduler.observations) == orig_length + 1
    assert scheduler.observations['Added Field'].exptime == 60 * u.second


def test_remove_field(scheduler):
    orig_keys = list(scheduler.observations.keys())

    # First remove a non-existing field, which should do nothing
    scheduler.remove_observation('123456789')
    assert orig_keys == list(scheduler.observations.keys())

    scheduler.remove_observation('HD 189733')
    assert orig_keys != list(scheduler.observations.keys())
