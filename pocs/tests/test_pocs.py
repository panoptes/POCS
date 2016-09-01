import os
import pytest

from pocs import POCS
from pocs import _check_config
from pocs import _check_environment
from pocs.utils.config import load_config
from pocs.utils.database import PanMongo


@pytest.fixture
def config():
    os.environ['POCS'] = os.getcwd()
    return load_config()


@pytest.fixture(scope='module')
def pocs():
    os.environ['POCSTIME'] = '2016-08-13 13:00:00'
    pocs = POCS(simulator=['all'])

    pocs.observatory.scheduler.fields_list = [
        {'name': 'Wasp 33',
         'position': '02h26m51.0582s +37d33m01.733s',
         'priority': '100',
         'exp_time': 2,
         'min_nexp': 2,
         'exp_set_size': 2,
         },
    ]

    return pocs


def test_simple_simulator(pocs):
    assert isinstance(pocs, POCS)


def test_not_initialized(pocs):
    assert pocs.is_initialized is not True


def test_run_without_initialize(pocs):
    with pytest.raises(AssertionError):
        pocs.run()


def test_initialization(pocs):
    pocs.initialize()
    assert pocs.is_initialized


def test_bad_pandir_env():
    pandir = os.getenv('PANDIR')
    os.environ['PANDIR'] = '/foo/bar'
    with pytest.raises(SystemExit):
        _check_environment()
    os.environ['PANDIR'] = pandir


def test_bad_pocs_env():
    pocs = os.getenv('POCS')
    os.environ['POCS'] = '/foo/bar'
    with pytest.raises(SystemExit):
        _check_environment()
    os.environ['POCS'] = pocs


def test_check_config1(config):
    del config['mount']
    with pytest.raises(SystemExit):
        _check_config(config)


def test_check_config2(config):
    del config['directories']
    with pytest.raises(SystemExit):
        _check_config(config)


def test_check_config3(config):
    del config['state_machine']
    with pytest.raises(SystemExit):
        _check_config(config)


def test_make_log_dir():
    log_dir = "{}/logs".format(os.getcwd())
    assert os.path.exists(log_dir) is False

    os.environ['PANDIR'] = os.getcwd()
    _check_environment()

    assert os.path.exists(log_dir) is True
    os.removedirs(log_dir)


def test_is_dark_simulator(pocs):
    pocs.config['simulator'] = ['camera', 'mount', 'weather', 'night']
    os.environ['POCSTIME'] = '2016-08-13 13:00:00'
    assert pocs.is_dark() is True

    os.environ['POCSTIME'] = '2016-08-13 23:00:00'
    assert pocs.is_dark() is True


def test_is_dark_no_simulator(pocs):
    pocs.config['simulator'] = ['camera', 'mount', 'weather']
    os.environ['POCSTIME'] = '2016-08-13 13:00:00'
    assert pocs.is_dark() is True

    os.environ['POCSTIME'] = '2016-08-13 23:00:00'
    assert pocs.is_dark() is False


def test_is_weather_safe_simulator(pocs):
    pocs.config['simulator'] = ['camera', 'mount', 'weather']
    assert pocs.is_weather_safe() is True


def test_is_weather_safe_no_simulator(pocs):
    pocs.config['simulator'] = ['camera', 'mount', 'weather', 'night']

    db = PanMongo()

    # Insert a dummy weather record
    db.insert_current('weather', {'safe': True})
    assert pocs.is_weather_safe() is True

    os.environ['POCSTIME'] = '2016-08-13 23:03:01'
    assert pocs.is_weather_safe() is False


def test_power_down(pocs):
    assert pocs.state == 'sleeping'
    pocs.get_ready()
    assert pocs.state == 'ready'
    pocs.power_down()
    assert pocs.state == 'parked'
    pocs.clean_up()
    pocs.goto_sleep()


def test_run_no_targets_and_exit(pocs):
    pocs.state = 'sleeping'
    pocs._do_states = True

    pocs.initialize()
    assert pocs.is_initialized is True
    pocs.run(exit_when_done=True)
    assert pocs.state == 'housekeeping'
