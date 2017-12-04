import os
import pytest

from pocs.utils.config import load_config
from pocs.utils.database import PanMongo


def pytest_addoption(parser):
    parser.addoption("--with-hardware", nargs='+', default=[],
                     help="A comma separated list of hardware to test"
                     "List items can include: mount, camera, weather, or all")
    parser.addoption("--solve", action="store_true", default=False,
                     help="If tests that require solving should be run")


def pytest_collection_modifyitems(config, items):
    """ Modify tests to skip or not based on cli options

    Certain tests should only be run when the appropriate hardware is attached.
    These tests should be marked as follows:

    `@pytest.mark.hardware`: Run all hardware tests
    `@pytest.mark.with_camera`: Run tests with camera attached
    `@pytest.mark.with_mount`: Run tests with camera attached
    `@pytest.mark.with_weather`: Run tests with camera attached

    Note:
        We are marking which tests to skip rather than which tests to include
        so the logic is opposite of the options
    """

    hardware_list = config.getoption('--with-hardware')

    if 'all' in hardware_list:
        has_camera = True
        has_mount = True
        has_weather = True
    else:
        has_camera = 'camera' in hardware_list
        has_mount = 'mount' in hardware_list
        has_weather = 'weather' in hardware_list

    skip_camera = pytest.mark.skip(reason="need --camera-test option to run")
    skip_mount = pytest.mark.skip(reason="need --mount-test option to run")
    skip_weather = pytest.mark.skip(reason="need --weather-test option to run")

    for marker in items:
        if "with_camera" in marker.keywords and not has_camera:
            marker.add_marker(skip_camera)

        if "with_mount" in marker.keywords and not has_mount:
            marker.add_marker(skip_mount)

        if "with_weather" in marker.keywords and not has_weather:
            marker.add_marker(skip_weather)


@pytest.fixture
def config():
    config = load_config(ignore_local=True, simulator=['all'])
    config['db']['name'] = 'panoptes_testing'
    return config


@pytest.fixture
def db():
    return PanMongo(db='panoptes_testing')


@pytest.fixture
def data_dir():
    return '{}/pocs/tests/data'.format(os.getenv('POCS'))
