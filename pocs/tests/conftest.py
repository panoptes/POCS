import os
import pytest

from pocs import hardware
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

    Certain tests should only be run when the appropriate hardware is attached. The names of the
    types of hardware are in hardware.py, but include 'mount' and 'camera'. For a test that
    requires a mount, for example, the test should be marked as follows:

    `@pytest.mark.with_mount`: Run tests with mount attached.

    And the same applies for the names of other types of hardware.

    Note:
        We are marking which tests to skip rather than which tests to include
        so the logic is opposite of the options.
    """

    hardware_list = config.getoption('--with-hardware')
    for name in hardware.get_all_names():
        # Do we have hardware called name?
        if name in hardware_list:
            # Yes, so don't need to skip tests with keyword "with_name".
            continue
        # No, so find all the tests that need this type of hardware and mark them to be skipped.
        skip = pytest.mark.skip(reason="need --with-hardware={} option to run".format(name))
        keyword = 'with_' + name
        for item in items:
            if keyword in item.keywords:
                item.add_marker(skip)


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


@pytest.fixture
def temp_file():
    temp_file = 'temp'
    with open(temp_file, 'w') as f:
        f.write('')

    yield temp_file
    os.unlink(temp_file)
