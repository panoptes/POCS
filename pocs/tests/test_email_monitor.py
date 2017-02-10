import pytest

from pocs.utils.too.email_monitor import *


@pytest.fixture
def config_filename():
    return 'config_donotread_1ocal'


@pytest.fixture
def host():
    return 'imap.gmail.com'


@pytest.fixture
def email():
    return 'bernie.telalovic@gmail.com'


@pytest.fixture
def password():
    return 'hdzlezqobwooqdqt'


@pytest.fixture
def alert_pocs():
    return True


@pytest.fixture
def selection_criteria():
    return ''


@pytest.fixture
def rescan_interval():
    return 0.1


def test_create_monitors(config_filename, host, email, password, alert_pocs, selection_criteria):

    monitors = create_monitors(config_filename, host, email, password, alert_pocs, selection_criteria, True)

    assert len(monitors) == 3


def test_loop_over_monitors(config_filename, host, email, password, alert_pocs, rescan_interval, selection_criteria):

    monitors = create_monitors(config_filename, host, email, password, alert_pocs, selection_criteria, True)

    for monitor in monitors:

        targets = loop_each_monitor(monitor[0], rescan_interval, [monitor[1][0]])

        assert len(targets) > 0
