import os
import pytest

from pocs.dome.simulator import Dome


@pytest.fixture(scope="function")
def dome(config):
    dome = Dome()
    yield dome
    dome.disconnect()


def test_create(dome):
    assert isinstance(dome, Dome)
    assert not dome.is_connected


def test_connect(dome):
    assert not dome.is_connected
    assert dome.connect() is True
    assert dome.is_connected is True
    # Can repeat.
    assert dome.connect() is True
    assert dome.is_connected is True


def test_disconnect(dome):
    assert dome.connect() is True
    assert dome.disconnect() is True
    assert dome.is_connected is False
    # Can repeat.
    assert dome.disconnect() is True
    assert dome.is_connected is False


def test_open_and_close_slit(dome):
    dome.connect()

    assert dome.open() is True
    assert dome.state == 'Open'
    assert dome.is_open is True

    assert dome.close() is True
    assert dome.state == 'Closed'
    assert dome.is_closed is True

    assert dome.disconnect() is True
