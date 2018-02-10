# This is in the root POCS directory so that pytest will recognize the
# options added below without having to also specify pocs/test, or a
# one of the tests in that directory, on the command line; i.e. pytest
# doesn't load pocs/tests/conftest.py until after it has searched for
# tests.

import os
import pytest

from pocs import hardware
from pocs.utils.logger import get_root_logger


def pytest_addoption(parser):
    hw_names = ",".join(hardware.get_all_names()) + ' (or all for all hardware)'
    group = parser.getgroup("PANOPTES pytest options")
    group.addoption(
        "--with-hardware",
        nargs='+',
        default=[],
        help=("A comma separated list of hardware to test. " + "List items can include: " +
              hw_names))
    group.addoption(
        "--without-hardware",
        nargs='+',
        default=[],
        help=("A comma separated list of hardware to NOT test. " + "List items can include: " +
              hw_names))
    group.addoption(
        "--solve",
        action="store_true",
        default=False,
        help="If tests that require solving should be run")
    group.addoption(
        "--test-cloud-storage",
        action="store_true",
        default=False,
        dest="test_cloud_storage",
        help="Tests cloud strorage functions." +
        "Requires $PANOPTES_CLOUD_KEY to be set to path of valid json service key")


def pytest_collection_modifyitems(config, items):
    """Modify tests to skip or not based on cli options.

    Certain tests should only be run when the appropriate hardware is attached.
    Other tests fail if real hardware is attached (e.g. they expect there is no
    hardware). The names of the types of hardware are in hardware.py, but
    include 'mount' and 'camera'. For a test that requires a mount, for
    example, the test should be marked as follows:

    `@pytest.mark.with_mount`

    And the same applies for the names of other types of hardware.
    For a test that requires that there be no cameras attached, mark the test
    as follows:

    `@pytest.mark.without_camera`
    """

    # without_hardware is a list of hardware names whose tests we don't want to run.
    without_hardware = hardware.get_simulator_names(
        simulator=config.getoption('--without-hardware'))

    # with_hardware is a list of hardware names for which we have that hardware attached.
    with_hardware = hardware.get_simulator_names(simulator=config.getoption('--with-hardware'))

    for name in without_hardware:
        # User does not want to run tests that interact with hardware called name,
        # whether it is marked as with_name or without_name.
        if name in with_hardware:
            print('Warning: {!r} in both --with-hardware and --without-hardware'.format(name))
            with_hardware.remove(name)
        skip = pytest.mark.skip(reason="--without-hardware={} specified".format(name))
        with_keyword = 'with_' + name
        without_keyword = 'without_' + name
        for item in items:
            if with_keyword in item.keywords or without_keyword in item.keywords:
                item.add_marker(skip)

    for name in hardware.get_all_names(without=with_hardware):
        # We don't have hardware called name, so find all tests that need that
        # hardware and mark it to be skipped.
        skip = pytest.mark.skip(reason="Test needs --with-hardware={} option to run".format(name))
        keyword = 'with_' + name
        for item in items:
            if keyword in item.keywords:
                item.add_marker(skip)


def pytest_runtest_logstart(nodeid, location):
    """Signal the start of running a single test item.

    This hook will be called before pytest_runtest_setup(),
    pytest_runtest_call() and pytest_runtest_teardown() hooks.

    Args:
        nodeid (str) – full id of the item
        location – a triple of (filename, linenum, testname)
    """
    logger = get_root_logger()
    logger.critical('')
    logger.critical('##########' * 8)
    logger.critical('     START TEST {}', nodeid)
    logger.critical('')


def pytest_runtest_logfinish(nodeid, location):
    """Signal the complete finish of running a single test item.

    This hook will be called after pytest_runtest_setup(),
    pytest_runtest_call() and pytest_runtest_teardown() hooks.

    Args:
        nodeid (str) – full id of the item
        location – a triple of (filename, linenum, testname)
    """
    logger = get_root_logger()
    logger.critical('')
    logger.critical('       END TEST {}', nodeid)
    logger.critical('')
    logger.critical('##########' * 8)


@pytest.fixture
def temp_file():
    temp_file = 'temp'
    with open(temp_file, 'w') as f:
        f.write('')

    yield temp_file
    os.unlink(temp_file)
