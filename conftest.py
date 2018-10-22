# This is in the root POCS directory so that pytest will recognize the
# options added below without having to also specify pocs/test, or a
# one of the tests in that directory, on the command line; i.e. pytest
# doesn't load pocs/tests/conftest.py until after it has searched for
# tests.
# In addition, there are fixtures defined here that are available to
# all tests, not just those in pocs/tests.

import copy
import os
import pytest
import subprocess
import time

from pocs import hardware
from pocs.utils.database import PanDB
from pocs.utils.logger import get_root_logger
from pocs.utils.messaging import PanMessaging

# Global variable set to a bool by can_connect_to_mongo().
_can_connect_to_mongo = None
_all_databases = ['mongo', 'file', 'memory']


def pytest_addoption(parser):
    hw_names = ",".join(hardware.get_all_names()) + ' (or all for all hardware)'
    db_names = ",".join(_all_databases) + ' (or all for all databases)'
    group = parser.getgroup("PANOPTES pytest options")
    group.addoption(
        "--with-hardware",
        nargs='+',
        default=[],
        help=("A comma separated list of hardware to test. List items can include: " + hw_names))
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
    group.addoption(
        "--test-databases",
        nargs="+",
        default=['mongo'],
        help=("Test databases in the list. List items can include: " + db_names +
              ". Note that travis-ci will test all of them by default."))


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
    try:
        logger = get_root_logger()
        logger.critical('')
        logger.critical('##########' * 8)
        logger.critical('     START TEST {}', nodeid)
        logger.critical('')
    except Exception:
        pass


def pytest_runtest_logfinish(nodeid, location):
    """Signal the complete finish of running a single test item.

    This hook will be called after pytest_runtest_setup(),
    pytest_runtest_call() and pytest_runtest_teardown() hooks.

    Args:
        nodeid (str) – full id of the item
        location – a triple of (filename, linenum, testname)
    """
    try:
        logger = get_root_logger()
        logger.critical('')
        logger.critical('       END TEST {}', nodeid)
        logger.critical('')
        logger.critical('##########' * 8)
    except Exception:
        pass


def pytest_runtest_logreport(report):
    """Adds the failure info that pytest prints to stdout into the log."""
    if report.skipped or report.outcome != 'failed':
        return
    try:
        logger = get_root_logger()
        logger.critical('')
        logger.critical('  TEST {} FAILED during {}\n\n{}\n', report.nodeid, report.when,
                        report.longreprtext)
        cnt = 15
        if report.capstdout:
            logger.critical('{}Captured stdout during {}{}\n{}\n', '= ' * cnt, report.when,
                            ' =' * cnt, report.capstdout)
        if report.capstderr:
            logger.critical('{}Captured stderr during {}{}\n{}\n', '* ' * cnt, report.when,
                            ' *' * cnt, report.capstderr)
    except Exception:
        pass


@pytest.fixture
def temp_file():
    temp_file = 'temp'
    with open(temp_file, 'w') as f:
        f.write('')

    yield temp_file
    os.unlink(temp_file)


class FakeLogger:
    def __init__(self):
        self.messages = []
        pass

    def _add(self, name, *args):
        msg = [name]
        assert len(args) == 1
        assert isinstance(args[0], tuple)
        msg.append(args[0])
        self.messages.append(msg)

    def debug(self, *args):
        self._add('debug', args)

    def info(self, *args):
        self._add('info', args)

    def warning(self, *args):
        self._add('warning', args)

    def error(self, *args):
        self._add('error', args)

    def critical(self, *args):
        self._add('critical', args)


@pytest.fixture(scope='function')
def fake_logger():
    return FakeLogger()


def can_connect_to_mongo():
    global _can_connect_to_mongo
    if _can_connect_to_mongo is None:
        logger = get_root_logger()
        try:
            PanDB(db_type='mongo', db_name='panoptes_testing', logger=logger, connect=True)
            _can_connect_to_mongo = True
        except Exception:
            _can_connect_to_mongo = False
        logger.info('can_connect_to_mongo = {}', _can_connect_to_mongo)
    return _can_connect_to_mongo


@pytest.fixture(scope='function', params=_all_databases)
def db_type(request):

    db_list = pytest.config.option.test_databases
    if request.param not in db_list and 'all' not in db_list:
        pytest.skip("Skipping {} DB, set --test-all-databases=True".format(request.param))

    # If testing mongo, make sure we can connect, otherwise skip.
    if request.param == 'mongo' and not can_connect_to_mongo():
        pytest.skip("Can't connect to {} DB, skipping".format(request.param))
    PanDB.permanently_erase_database(
        request.param, 'panoptes_testing', really='Yes', dangerous='Totally')
    return request.param


@pytest.fixture(scope='function')
def db(db_type):
    return PanDB(
        db_type=db_type, db_name='panoptes_testing', logger=get_root_logger(), connect=True)


@pytest.fixture(scope='function')
def memory_db():
    PanDB.permanently_erase_database(
        'memory', 'panoptes_testing', really='Yes', dangerous='Totally')
    return PanDB(db_type='memory', db_name='panoptes_testing')


# -----------------------------------------------------------------------
# Messaging support fixtures. It is important that tests NOT use the same
# ports that the real pocs_shell et al use; when they use the same ports,
# then tests may cause errors in the real system (e.g. by sending a
# shutdown command).


@pytest.fixture(scope='module')
def messaging_ports():
    # Some code (e.g. POCS._setup_messaging) assumes that sub and pub ports
    # are sequential so these need to match that assumption for now.
    return dict(msg_ports=(43001, 43002), cmd_ports=(44001, 44002))


@pytest.fixture(scope='function')
def message_forwarder(messaging_ports):
    cmd = os.path.join(os.getenv('POCS'), 'scripts', 'run_messaging_hub.py')
    args = [cmd]
    # Note that the other programs using these port pairs consider
    # them to be pub and sub, in that order, but the forwarder sees things
    # in reverse: it subscribes to the port that others publish to,
    # and it publishes to the port that others subscribe to.
    for _, (sub, pub) in messaging_ports.items():
        args.append('--pair')
        args.append(str(sub))
        args.append(str(pub))

    get_root_logger().info('message_forwarder fixture starting: {}', args)
    proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # It takes a while for the forwarder to start, so allow for that.
    # TODO(jamessynge): Come up with a way to speed up these fixtures.
    time.sleep(3)
    yield messaging_ports
    proc.terminate()


@pytest.fixture(scope='function')
def msg_publisher(message_forwarder):
    port = message_forwarder['msg_ports'][0]
    publisher = PanMessaging.create_publisher(port)
    yield publisher
    publisher.close()


@pytest.fixture(scope='function')
def msg_subscriber(message_forwarder):
    port = message_forwarder['msg_ports'][1]
    subscriber = PanMessaging.create_subscriber(port)
    yield subscriber
    subscriber.close()


@pytest.fixture(scope='function')
def cmd_publisher(message_forwarder):
    port = message_forwarder['cmd_ports'][0]
    publisher = PanMessaging.create_publisher(port)
    yield publisher
    publisher.close()


@pytest.fixture(scope='function')
def cmd_subscriber(message_forwarder):
    port = message_forwarder['cmd_ports'][1]
    subscriber = PanMessaging.create_subscriber(port)
    yield subscriber
    subscriber.close()


@pytest.fixture(scope='function')
def save_environ():
    old_env = copy.deepcopy(os.environ)
    yield
    os.environ = old_env


@pytest.fixture(scope='session')
def data_dir():
    return os.path.join(os.getenv('POCS'), 'pocs', 'tests', 'data')


@pytest.fixture(scope='session')
def unsolved_fits_file(data_dir):
    return os.path.join(data_dir, 'unsolved.fits')


@pytest.fixture(scope='session')
def solved_fits_file(data_dir):
    return os.path.join(data_dir, 'solved.fits.fz')


@pytest.fixture(scope='session')
def tiny_fits_file(data_dir):
    return os.path.join(data_dir, 'tiny.fits')


@pytest.fixture(scope='session')
def noheader_fits_file(data_dir):
    return os.path.join(data_dir, 'noheader.fits')
