import time
import pytest
from multiprocessing import Process

from astropy import units as u

from pocs import hardware
from pocs.scheduler.field import Field
from pocs.scheduler.observation import Observation
from panoptes.utils.logger import get_root_logger
from panoptes.utils.config.client import set_config
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
def field(config_port):
    return Field('Test Observation', '20h00m43.7135s +22d42m39.0645s', config_port=config_port)


def test_create_observation_no_field(config_port):
    with pytest.raises(TypeError):
        Observation(config_port=config_port)


def test_create_observation_bad_field(config_port):
    with pytest.raises(AssertionError):
        Observation('20h00m43.7135s +22d42m39.0645s', config_port=config_port)


def test_create_observation_exptime_no_units(field, config_port):
    with pytest.raises(TypeError):
        Observation(field, exptime=1.0, config_port=config_port)


def test_create_observation_exptime_bad(field, config_port):
    with pytest.raises(AssertionError):
        Observation(field, exptime=0.0 * u.second, config_port=config_port)


def test_create_observation_exptime_minutes(field, config_port):
    obs = Observation(field, exptime=5.0 * u.minute, config_port=config_port)
    assert obs.exptime == 300 * u.second


def test_bad_priority(field, config_port):
    with pytest.raises(AssertionError):
        Observation(field, priority=-1, config_port=config_port)


def test_good_priority(field, config_port):
    obs = Observation(field, priority=5.0, config_port=config_port)
    assert obs.priority == 5.0


def test_priority_str(field, config_port):
    obs = Observation(field, priority="5", config_port=config_port)
    assert obs.priority == 5.0


def test_bad_min_set_combo(field, config_port):
    with pytest.raises(AssertionError):
        Observation(field, exp_set_size=7, config_port=config_port)
    with pytest.raises(AssertionError):
        Observation(field, min_nexp=57, config_port=config_port)


def test_small_sets(field, config_port):
    obs = Observation(field, exptime=1 * u.second, min_nexp=1,
                      exp_set_size=1, config_port=config_port)
    assert obs.minimum_duration == 1 * u.second
    assert obs.set_duration == 1 * u.second


def test_good_min_set_combo(field, config_port):
    obs = Observation(field, min_nexp=21, exp_set_size=3, config_port=config_port)
    assert isinstance(obs, Observation)


def test_default_min_duration(field, config_port):
    obs = Observation(field, config_port=config_port)
    assert obs.minimum_duration == 7200 * u.second


def test_default_set_duration(field, config_port):
    obs = Observation(field, config_port=config_port)
    assert obs.set_duration == 1200 * u.second


def test_print(field, config_port):
    obs = Observation(field, exptime=17.5 * u.second, min_nexp=27,
                      exp_set_size=9, config_port=config_port)
    test_str = "Test Observation: 17.5 s exposures in blocks of 9, minimum 27, priority 100"
    assert str(obs) == test_str


def test_seq_time(field, config_port):
    obs = Observation(field, exptime=17.5 * u.second, min_nexp=27,
                      exp_set_size=9, config_port=config_port)
    assert obs.seq_time is None


def test_no_exposures(field, config_port):
    obs = Observation(field, exptime=17.5 * u.second, min_nexp=27,
                      exp_set_size=9, config_port=config_port)
    assert obs.first_exposure is None
    assert obs.last_exposure is None
    assert obs.pointing_image is None


def test_last_exposure_and_reset(field, config_port):
    obs = Observation(field, exptime=17.5 * u.second, min_nexp=27,
                      exp_set_size=9, config_port=config_port)
    status = obs.status()
    assert status['current_exp'] == obs.current_exp_num

    # Mimic taking exposures
    obs.merit = 112.5

    for i in range(5):
        obs.exposure_list['image_{}'.format(i)] = 'full_image_path_{}'.format(i)

    last = obs.last_exposure
    assert isinstance(last, tuple)
    assert obs.merit > 0.0
    assert obs.current_exp_num == 5

    assert last[0] == 'image_4'
    assert last[1] == 'full_image_path_4'

    assert isinstance(obs.first_exposure, tuple)
    assert obs.first_exposure[0] == 'image_0'
    assert obs.first_exposure[1] == 'full_image_path_0'

    obs.reset()
    status2 = obs.status()

    assert status2['current_exp'] == 0
    assert status2['merit'] == 0.0
    assert obs.first_exposure is None
    assert obs.last_exposure is None
    assert obs.seq_time is None
