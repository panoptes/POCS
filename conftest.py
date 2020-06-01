import logging
import os
import stat
import pytest
from _pytest.logging import caplog as _caplog
import subprocess
import time
import tempfile
import shutil

from contextlib import suppress
from multiprocessing import Process
from scalpl import Cut

from panoptes.pocs import hardware
from panoptes.utils.database import PanDB
from panoptes.utils.config import load_config
from panoptes.utils.config.client import set_config
from panoptes.utils.config.server import app as config_server_app

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
logger.add(log_file_path,
           format=LOGGER_INFO.format,
           colorize=True,
           enqueue=True,  # multiprocessing
           backtrace=True,
           diagnose=True,
           level='TRACE')
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
        "--solve",
        action="store_true",
        default=False,
        help="If tests that require solving should be run")
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
    try:
        logger.log('testing', '')
        logger.log('testing', f'  TEST {report.nodeid} FAILED during {report.when} {report.longreprtext} ')
        if report.capstdout:
            logger.log('testing', f'============ Captured stdout during {report.when} {report.capstdout} ============')
        if report.capstderr:
            logger.log('testing', f'============ Captured stdout during {report.when} {report.capstderr} ============')
    except Exception:
        pass


@pytest.fixture(scope='session')
def db_name():
    return 'panoptes_testing'


@pytest.fixture(scope='session')
def images_dir(tmpdir_factory):
    directory = tmpdir_factory.mktemp('images')
    return str(directory)


@pytest.fixture(scope='session')
def config_host():
    return 'localhost'


@pytest.fixture(scope='session')
def static_config_port():
    """Used for the session-scoped config_server where no config values
    are expected to change during testing.
    """
    return '6563'


@pytest.fixture(scope='module')
def config_port():
    """Used for the function-scoped config_server when it is required to change
    config values during testing. See `dynamic_config_server` docs below.
    """
    return '4861'


@pytest.fixture(scope='session')
def config_path():
    return os.path.join(os.getenv('POCS'), 'tests', 'pocs_testing.yaml')


@pytest.fixture(scope='session')
def config_server_args(config_path):
    loaded_config = load_config(config_files=config_path, ignore_local=True)
    return {
        'config_file': config_path,
        'auto_save': False,
        'ignore_local': True,
        'POCS': loaded_config,
        'POCS_cut': Cut(loaded_config)
    }


def make_config_server(config_host, config_port, config_server_args, images_dir, db_name):
    def start_config_server():
        # Load the config items into the app config.
        for k, v in config_server_args.items():
            config_server_app.config[k] = v

        # Start the actual flask server.
        config_server_app.run(host=config_host, port=config_port)

    proc = Process(target=start_config_server)
    proc.start()

    logger.log('testing', f'config_server started with PID={proc.pid}')

    # Give server time to start
    time.sleep(1)

    # Adjust various config items for testing
    unit_name = 'Generic PANOPTES Unit'
    unit_id = 'PAN000'
    logger.log('testing', f'Setting testing name and unit_id to {unit_id}')
    set_config('name', unit_name, port=config_port)
    set_config('pan_id', unit_id, port=config_port)

    logger.log('testing', f'Setting testing database to {db_name}')
    set_config('db.name', db_name, port=config_port)

    fields_file = 'simulator.yaml'
    logger.log('testing', f'Setting testing scheduler fields_file to {fields_file}')
    set_config('scheduler.fields_file', fields_file, port=config_port)

    # TODO(wtgee): determine if we need separate directories for each module.
    logger.log('testing', f'Setting temporary image directory for testing')
    set_config('directories.images', images_dir, port=config_port)

    # Make everything a simulator
    simulators = hardware.get_simulator_names(simulator=['all'])
    logger.log('testing', f'Setting all hardware to use simulators: {simulators}')
    set_config('simulator', simulators, port=config_port)

    return proc


@pytest.fixture(scope='session', autouse=True)
def static_config_server(config_host, static_config_port, config_server_args, images_dir, db_name):
    logger.log('testing', f'Starting config_server for testing session')
    proc = make_config_server(config_host, static_config_port, config_server_args, images_dir, db_name)
    yield proc
    pid = proc.pid
    proc.terminate()
    time.sleep(0.1)
    logger.log('testing', f'Killed config_server started with PID={pid}')


@pytest.fixture(scope='function')
def dynamic_config_server(config_host, config_port, config_server_args, images_dir, db_name):
    """If a test requires changing the configuration we use a function-scoped testing
    server. We only do this on tests that require it so we are not constantly starting and stopping
    the config server unless necessary.  To use this, each test that requires it must use the
    `dynamic_config_server` and `config_port` fixtures and must pass the `config_port` to all
    instances that are created (propagated through PanBase).
    """

    logger.log('testing', f'Starting config_server for testing function')
    proc = make_config_server(config_host, config_port, config_server_args, images_dir, db_name)

    yield proc
    pid = proc.pid
    proc.terminate()
    time.sleep(0.1)
    logger.log('testing', f'Killed config_server started with PID={pid}')


@pytest.fixture
def temp_file(tmp_path):
    d = tmp_path
    d.mkdir(exist_ok=True)
    f = d / 'temp'
    yield f
    f.unlink(missing_ok=True)


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
    return '/var/panoptes/panoptes-utils/tests/data'


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
