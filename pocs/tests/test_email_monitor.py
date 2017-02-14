import pytest

from pocs.utils.too.email_monitor import *


@pytest.fixture
def config_filename():
    return 'email_parsers'


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

    monitors = create_monitors(config_filename, host, email, password, alert_pocs, selection_criteria, True, True)

    assert len(monitors) == 3


def test_read_email_in_monitor(config_filename, host, email, password, alert_pocs, rescan_interval, selection_criteria):

    monitors = create_monitors(config_filename, host, email, password, alert_pocs, selection_criteria, True, True)

    for monitor in monitors:

        targets = read_email_in_monitor(monitor[0], [monitor[1][0]])

        assert len(targets) > 0
