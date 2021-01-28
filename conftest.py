import logging
import os
import shutil
import stat
import tempfile
from contextlib import suppress

import pytest
from _pytest.logging import caplog as _caplog  # noqa
from panoptes.pocs import hardware
from panoptes.pocs.utils.logger import get_logger
from panoptes.pocs.utils.logger import PanLogger
from panoptes.utils.config.client import set_config
from panoptes.utils.config.server import config_server

# TODO download IERS files.

_all_databases = ['file', 'memory']

TESTING_LOG_LEVEL = 'TRACE'
LOGGER_INFO = PanLogger()

logger = get_logger(console_log_level=TESTING_LOG_LEVEL)
logger.enable('panoptes')
# Add a level above TRACE and below DEBUG
logger.level("testing", no=15, icon="🤖", color="<LIGHT-BLUE><white>")
log_fmt = "<lvl>{level:.1s}</lvl> " \
          "<light-blue>{time:MM-DD HH:mm:ss.SSS!UTC}</>" \
          "<blue> ({time:HH:mm:ss zz})</> " \
          "| <c>{name} {function}:{line}</c> | " \
          "<lvl>{message}</lvl>"

log_dir = os.getenv('PANLOG', 'logs')
log_file_path = os.path.join(log_dir, 'panoptes-testing.log')
startup_message = f' STARTING NEW PYTEST RUN - LOGS: {log_file_path} '
logger.add(log_file_path,
           enqueue=True,  # multiprocessing
           format=log_fmt,
           colorize=True,
           # TODO decide on these options
           backtrace=True,
           diagnose=True,
           catch=True,
           # Start new log file for each testing run.
           rotation=lambda msg, _: startup_message in msg,
           level=TESTING_LOG_LEVEL)

logger.log('testing', '*' * 25 + startup_message + '*' * 25)

# Make the log file world readable.
os.chmod(log_file_path, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)


def pytest_configure(config):
    """Set up the testing."""
    logger.info('Setting up the config server.')
    config_file = 'tests/testing.yaml'

    host = 'localhost'
    port = '8765'

    os.environ['PANOPTES_CONFIG_HOST'] = host
    os.environ['PANOPTES_CONFIG_PORT'] = port

    config_server(config_file, host=host, port=port, load_local=False, save_local=False)
    logger.success('Config server set up')


def pytest_addoption(parser):
    hw_names = ",".join(hardware.get_all_names()) + ' (or all for all hardware)'
    db_names = ",".join(_all_databases) + ' (or all for all databases)'
    group = parser.getgroup("PANOPTES pytest options")
    group.addoption(
        "--with-hardware",
        nargs='+',
        default=[],
        help=f"A comma separated list of hardware to test. List items can include: {hw_names}")
    group.addoption(
        "--without-hardware",
        nargs='+',
        default=[],
        help=f"A comma separated list of hardware to NOT test.  List items can include: {hw_names}")
    group.addoption(
        "--test-databases",
        nargs="+",
        default=['file'],
        help=f"Test databases in the list. List items can include: {db_names}. Note that "
             f"travis-ci will test all of "
             f"them by default.")
    group.addoption(
        "--theskyx",
        action='store_true',
        default=False,
        help=f"Test TheSkyX commands, default False -- CURRENTLY NOT WORKING!")


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

    for name in without_hardware:  # noqa
        # User does not want to run tests that interact with hardware called name,
        # whether it is marked as with_name or without_name.
        if name in with_hardware:
            print(f'Warning: {name} in both --with-hardware and --without-hardware')
            with_hardware.remove(name)
        skip = pytest.mark.skip(reason=f"--without-hardware={name} specified")
        with_keyword = f'with_{name}'
        without_keyword = f'without_{name}'
        for item in items:
            if with_keyword in item.keywords or without_keyword in item.keywords:
                item.add_marker(skip)

    for name in hardware.get_all_names(without=with_hardware):
        # We don't have hardware called name, so find all tests that need that
        # hardware and mark it to be skipped.
        skip = pytest.mark.skip(reason=f"Test needs --with-hardware={name} option to run")
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
    with suppress(Exception):
        logger.log('testing', '##########' * 8)
        logger.log('testing', f'     START TEST {nodeid}')
        logger.log('testing', '')


def pytest_runtest_logfinish(nodeid, location):
    """Signal the complete finish of running a single test item.
    This hook will be called after pytest_runtest_setup(),
    pytest_runtest_call() and pytest_runtest_teardown() hooks.
    Args:
        nodeid (str) – full id of the item
        location – a triple of (filename, linenum, testname)
    """
    with suppress(Exception):
        logger.log('testing', '')
        logger.log('testing', f'       END TEST {nodeid}')
        logger.log('testing', '##########' * 8)


@pytest.fixture(scope='session')
def config_host():
    return os.getenv('PANOPTES_CONFIG_HOST', 'localhost')


@pytest.fixture(scope='session')
def config_port():
    return os.getenv('PANOPTES_CONFIG_PORT', 6563)


@pytest.fixture
def temp_file(tmp_path):
    d = tmp_path
    d.mkdir(exist_ok=True)
    f = d / 'temp'
    yield f
    with suppress(FileNotFoundError):
        f.unlink()


@pytest.fixture(scope='session')
def images_dir(tmpdir_factory):
    directory = tmpdir_factory.mktemp('images')
    set_config('directories.images', str(directory))
    return str(directory)


@pytest.fixture(scope='session')
def data_dir():
    return os.path.expandvars('${POCS}/tests/data')


@pytest.fixture(scope='function')
def unsolved_fits_file(data_dir):
    orig_file = os.path.join(data_dir, 'unsolved.fits')

    with tempfile.TemporaryDirectory() as tmpdirname:
        copy_file = shutil.copy2(orig_file, tmpdirname)
        yield copy_file


@pytest.fixture(scope='function')
def solved_fits_file(data_dir):
    orig_file = os.path.join(data_dir, 'solved.fits.fz')

    with tempfile.TemporaryDirectory() as tmpdirname:
        copy_file = shutil.copy2(orig_file, tmpdirname)
        yield copy_file


@pytest.fixture(scope='function')
def tiny_fits_file(data_dir):
    orig_file = os.path.join(data_dir, 'tiny.fits')

    with tempfile.TemporaryDirectory() as tmpdirname:
        copy_file = shutil.copy2(orig_file, tmpdirname)
        yield copy_file


@pytest.fixture(scope='function')
def noheader_fits_file(data_dir):
    orig_file = os.path.join(data_dir, 'noheader.fits')

    with tempfile.TemporaryDirectory() as tmpdirname:
        copy_file = shutil.copy2(orig_file, tmpdirname)
        yield copy_file


@pytest.fixture(scope='function')
def cr2_file(data_dir):  # noqa
    cr2_path = os.path.join(data_dir, 'canon.cr2')

    if not os.path.exists(cr2_path):
        pytest.skip("No CR2 file found, skipping test.")

    return cr2_path


@pytest.fixture()
def caplog(_caplog):
    class PropagatedHandler(logging.Handler):
        def emit(self, record):
            logging.getLogger(record.name).handle(record)

    handler_id = logger.add(PropagatedHandler(), format="{message}")
    yield _caplog
    with suppress(ValueError):
        logger.remove(handler_id)
