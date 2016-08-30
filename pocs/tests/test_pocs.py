import os
import pytest

from pocs import POCS
from pocs import _check_config
from pocs import _check_environment
from pocs.utils.config import load_config


@pytest.fixture
def config():
    os.environ['POCS'] = os.getcwd()
    return load_config()


@pytest.fixture(scope='module')
def pocs():
    pocs = POCS(simulator=['all'])
    return pocs


def test_simple_simulator(pocs):
    assert isinstance(pocs, POCS)


def test_not_initialized(pocs):
    assert pocs.is_initialized is not True


def test_run_without_initilize(pocs):
    with pytest.raises(AssertionError):
        pocs.run()


def test_initialization(pocs):
    pocs.initialize()
    assert pocs.is_initialized


def test_bad_pandir_env():
    os.environ['PANDIR'] = '/foo/bar'
    with pytest.raises(SystemExit):
        _check_environment()


def test_bad_pocs_env():
    os.environ['POCS'] = '/foo/bar'
    with pytest.raises(SystemExit):
        _check_environment()


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
