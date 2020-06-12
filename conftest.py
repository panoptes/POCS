import logging
import os
import stat
import pytest
import time
import tempfile
import shutil
from contextlib import suppress
from _pytest.logging import caplog as _caplog

from panoptes.pocs import hardware
from panoptes.utils.database import PanDB
from panoptes.utils.config.client import get_config
from panoptes.utils.config.client import set_config
from panoptes.utils.config.server import config_server

from panoptes.pocs.utils.logger import get_logger, PanLogger

# TODO download IERS files.

_all_databases = ['file', 'memory']

LOGGER_INFO = PanLogger()

logger = get_logger()
logger.enable('panoptes')
logger.level("testing", no=15, icon="🤖", color="<YELLOW><black>")
log_file_path = os.path.join(
    os.getenv('PANLOG', '/var/panoptes/logs'),
    'panoptes-testing.log'
)
startup_message = ' STARTING NEW PYTEST RUN '
logger.add(log_file_path,
           enqueue=True,  # multiprocessing
           format=LOGGER_INFO.fmt,
           colorize=True,
           backtrace=True,
           diagnose=True,
           catch=True,
           # Start new log file for each testing run.
           rotation=lambda msg, _: startup_message in msg,
           level='TRACE')
logger.log('testing', '*' * 25 + startup_message + '*' * 25)
# Make the log file world readable.
os.chmod(log_file_path, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)


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
        help=f"Test databases in the list. List items can include: {db_names}. Note that travis-ci will test all of "
             f"them by default.")


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


def pytest_runtest_logreport(report):
    """Adds the failure info that pytest prints to stdout into the log."""
    if report.skipped or report.outcome != 'failed':
        return
    with suppress(Exception):
        logger.log('testing', '')
        logger.log('testing', f'  TEST {report.nodeid} FAILED during {report.when} {report.longreprtext} ')
        if report.capstdout:
            logger.log('testing', f'============ Captured stdout during {report.when} {report.capstdout} ============')
        if report.capstderr:
            logger.log('testing', f'============ Captured stdout during {report.when} {report.capstderr} ============')


@pytest.fixture(scope='session')
def config_path():
    return os.path.expandvars('${POCS}/tests/pocs_testing.yaml')


@pytest.fixture(scope='session', autouse=True)
def static_config_server(config_path, images_dir, db_name):
    logger.log('testing', f'Starting static_config_server for testing session')

    proc = config_server(
        config_path,
        ignore_local=True,
        auto_save=False
    )

    logger.log('testing', f'static_config_server started with {proc.pid=}')

    # Give server time to start
    while get_config('name') is None:  # pragma: no cover
        logger.log('testing', f'Waiting for static_config_server {proc.pid=}, sleeping 1 second.')
        time.sleep(1)

    logger.log('testing', f'Startup config_server name=[{get_config("name")}]')
    yield
    logger.log('testing', f'Killing static_config_server started with PID={proc.pid}')
    proc.terminate()


@pytest.fixture
def temp_file(tmp_path):
    d = tmp_path
    d.mkdir(exist_ok=True)
    f = d / 'temp'
    yield f
    f.unlink(missing_ok=True)


@pytest.fixture(scope='session')
def db_name():
    return 'panoptes_testing'


@pytest.fixture(scope='session')
def images_dir(tmpdir_factory):
    directory = tmpdir_factory.mktemp('images')
    return str(directory)


@pytest.fixture(scope='function', params=_all_databases)
def db_type(request, db_name):
    db_list = request.config.option.test_databases
    if request.param not in db_list and 'all' not in db_list:
        pytest.skip(f"Skipping {request.param} DB, set --test-all-databases=True")

    PanDB.permanently_erase_database(request.param, db_name, really='Yes', dangerous='Totally')
    return request.param


@pytest.fixture(scope='function')
def db(db_type, db_name):
    return PanDB(db_type=db_type, db_name=db_name, connect=True)


@pytest.fixture(scope='function')
def memory_db(db_name):
    PanDB.permanently_erase_database('memory', db_name, really='Yes', dangerous='Totally')
    return PanDB(db_type='memory', db_name=db_name)


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
def cr2_file(data_dir):
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
