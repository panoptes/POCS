import pytest

import os
from pocs_alerter.email_monitor import *


@pytest.fixture
def config_filename():
    pocs_dir = os.getenv('POCS')
    return pocs_dir + '/config_donotread_1ocal.yaml'


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


def test_load_config(config_filename):

    config = load_config(config_filename)

    assert len(config) > 0
    assert len(config['email_parsers']) > 0


def test_create_monitors(config_filename, host, email, password, alert_pocs):

    config = load_config(config_filename)

    monitors = create_monitors(config, host, email, password, alert_pocs)

    assert len(monitors) > 0
