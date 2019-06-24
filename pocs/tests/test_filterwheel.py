import os
import time
import pytest
import subprocess
import math
from timeit import timeit

from astropy import units as u

from pocs import hardware
from pocs.filterwheel.simulator import FilterWheel as SimFilterWheel
from pocs.camera.simulator import Camera as SimCamera
from panoptes.utils import error
from panoptes.utils.logger import get_root_logger
from panoptes.utils.config.client import set_config


@pytest.fixture(scope='module')
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


@pytest.fixture(scope='function')
def filterwheel(config_port):
    sim_filterwheel = SimFilterWheel(filter_names=['one', 'deux', 'drei', 'quattro'],
                                     move_time=0.1 * u.second,
                                     timeout=0.5 * u.second,
                                     config_port=config_port)
    return sim_filterwheel

# intialisation


def test_init(filterwheel):
    assert isinstance(filterwheel, SimFilterWheel)
    assert filterwheel.is_connected


def test_camera_init(config_port):
    sim_camera = SimCamera(filterwheel={'model': 'simulator',
                                        'filter_names': ['one', 'deux', 'drei', 'quattro']},
                           config_port=config_port)
    assert isinstance(sim_camera.filterwheel, SimFilterWheel)
    assert sim_camera.filterwheel.is_connected
    assert sim_camera.filterwheel.uid
    assert sim_camera.filterwheel.camera is sim_camera


def test_camera_no_filterwheel(config_port):
    sim_camera = SimCamera(config_port=config_port)
    assert sim_camera.filterwheel is None


def test_camera_association_on_init(config_port):
    sim_camera = SimCamera(config_port=config_port)
    sim_filterwheel = SimFilterWheel(filter_names=['one', 'deux', 'drei', 'quattro'],
                                     camera=sim_camera, config_port=config_port)
    assert sim_filterwheel.camera is sim_camera


def test_with_no_name(config_port):
    with pytest.raises(ValueError):
        SimFilterWheel(config_port=config_port)

# Basic property getting and (not) setting


def test_model(filterwheel):
    model = filterwheel.model
    assert model == 'simulator'
    with pytest.raises(AttributeError):
        filterwheel.model = "Airfix"


def test_name(filterwheel):
    name = filterwheel.name
    assert name == 'Simulated Filter Wheel'
    with pytest.raises(AttributeError):
        filterwheel.name = "Phillip"


def test_uid(filterwheel):
    uid = filterwheel.uid
    assert uid.startswith('SW')
    assert len(uid) == 6
    with pytest.raises(AttributeError):
        filterwheel.uid = "Can't touch this"


def test_filter_names(filterwheel):
    names = filterwheel.filter_names
    assert isinstance(names, list)
    for name in names:
        assert isinstance(name, str)
    with pytest.raises(AttributeError):
        filterwheel.filter_names = ["Unsharp mask", "Gaussian blur"]

# Movement


def test_move_number(filterwheel):
    assert filterwheel.position == 1
    e = filterwheel.move_to(2)
    assert math.isnan(filterwheel.position)  # position is NaN while between filters
    e.wait()
    assert filterwheel.position == 2
    e = filterwheel.move_to(3, blocking=True)
    assert e.is_set()
    assert filterwheel.position == 3
    filterwheel.position = 4  # Move by assignment to position property blocks until complete
    assert filterwheel.position == 4


def test_move_bad_number(filterwheel):
    with pytest.raises(ValueError):
        filterwheel.move_to(0, blocking=True)  # No zero based numbering here!
    with pytest.raises(ValueError):
        filterwheel.move_to(-1, blocking=True)  # Definitely not
    with pytest.raises(ValueError):
        filterwheel.position = 99  # Problems.
    with pytest.raises(ValueError):
        filterwheel.move_to(filterwheel._n_positions + 1, blocking=True)  # Close, but...
    filterwheel.move_to(filterwheel._n_positions, blocking=True)  # OK


def test_move_name(filterwheel, caplog):
    filterwheel.position = 1  # Start from a known position
    e = filterwheel.move_to('quattro')
    assert filterwheel.current_filter == 'UNKNOWN'  # I'm between filters right now
    e.wait()
    assert filterwheel.current_filter == 'quattro'
    e = filterwheel.move_to('o', blocking=True)  # Matches leading substrings too
    assert filterwheel.current_filter == 'one'
    filterwheel.position = 'd'  # In case of multiple matches logs a warning & uses the first match
    assert filterwheel.current_filter == 'deux'
    # WARNING followed by INFO level record about the move
    assert caplog.records[-2].levelname == 'WARNING'
    assert caplog.records[-1].levelname == 'INFO'
    filterwheel.position = 'deux'  # Check null move. Earlier version of simulator failed this!
    assert filterwheel.current_filter == 'deux'


def test_move_bad_name(filterwheel):
    with pytest.raises(ValueError):
        filterwheel.move_to('cinco')


def test_move_timeout(config_port, caplog):
    slow_filterwheel = SimFilterWheel(filter_names=['one', 'deux', 'drei', 'quattro'],
                                      move_time=0.1,
                                      timeout=0.2,
                                      config_port=config_port)
    slow_filterwheel.position = 4  # Move should take 0.3 seconds, more than timeout.
    time.sleep(0.001)  # For some reason takes a moment for the error to get logged.
    assert caplog.records[-1].levelname == 'ERROR'  # Should have logged an ERROR by now
    # It raises a panoptes.utils.error.Timeout exception too, but because it's in another Thread it
    # doesn't get passes up to the calling code.


@pytest.mark.parametrize("name,bidirectional, expected",
                         [("monodirectional", False, 0.3),
                          ("bidirectional", True, 0.1)])
def test_move_times(config_port, name, bidirectional, expected):
    sim_filterwheel = SimFilterWheel(filter_names=['one', 'deux', 'drei', 'quattro'],
                                     move_time=0.1 * u.second,
                                     move_bidirectional=bidirectional,
                                     timeout=0.5 * u.second,
                                     config_port=config_port)
    sim_filterwheel.position = 1
    assert timeit("sim_filterwheel.position = 2", number=1, globals=locals()) == \
        pytest.approx(0.1, rel=4e-2)
    assert timeit("sim_filterwheel.position = 4", number=1, globals=locals()) == \
        pytest.approx(0.2, rel=4e-2)
    assert timeit("sim_filterwheel.position = 3", number=1, globals=locals()) == \
        pytest.approx(expected, rel=4e-2)


def test_move_exposing(config_port, tmpdir, caplog):
    sim_camera = SimCamera(filterwheel={'model': 'simulator',
                                        'filter_names': ['one', 'deux', 'drei', 'quattro']},
                           config_port=config_port)
    fits_path = str(tmpdir.join('test_exposure.fits'))
    exp_event = sim_camera.take_exposure(filename=fits_path, seconds=0.1)
    with pytest.raises(error.PanError):
        # Attempt to move while camera is exposing
        sim_camera.filterwheel.move_to(2, blocking=True)
    assert caplog.records[-1].levelname == 'ERROR'
    assert sim_camera.filterwheel.position == 1  # Should not have moved
    exp_event.wait()


def test_is_moving(filterwheel):
    filterwheel.position = 1
    assert not filterwheel.is_moving
    e = filterwheel.move_to(2)
    assert filterwheel.is_moving
    e.wait()
    assert not filterwheel.is_moving
