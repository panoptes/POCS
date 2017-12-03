import os
import pytest

from pocs.utils.config import load_config
from pocs.utils.database import PanMongo


def pytest_addoption(parser):
    parser.addoption("--hardware-test", action="store_true", default=False,
                     help="Test with hardware attached")
    parser.addoption("--camera-test", action="store_true", default=False,
                     help="If a real camera attached")
    parser.addoption("--mount-test", action="store_true", default=False,
                     help="If a real mount attached")
    parser.addoption("--weather-test", action="store_true", default=False,
                     help="If a real weather station attached")
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
        The `--hardware-test` supersedes the other options, only use to test a
        fully attached unit.

    """

    has_all_hardware = config.getoption('--hardware-test')
    has_camera = config.getoption('--camera-test')
    has_mount = config.getoption('--mount-test')
    has_weather = config.getoption('--weather-test')

    skip_camera = False
    skip_mount = False
    skip_weather = False

    # If we have all hardware, don't add skip marker
    if has_all_hardware:
        return

    if not has_camera:
        skip_camera = pytest.mark.skip(reason="need --camera-test option to run")

    if not has_mount:
        skip_mount = pytest.mark.skip(reason="need --mount-test option to run")

    if not has_weather:
        skip_weather = pytest.mark.skip(reason="need --weather-test option to run")

    for item in items:
        if "with_camera" in item.keywords:
            item.add_marker(skip_camera)

        if "with_mount" in item.keywords:
            item.add_marker(skip_mount)

        if "with_weather" in item.keywords:
            item.add_marker(skip_weather)


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
