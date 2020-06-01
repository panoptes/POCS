import pytest

from panoptes.pocs.dome import simulator
from panoptes.pocs.dome import create_dome_simulator

from panoptes.utils.config.client import set_config


@pytest.fixture(scope="function")
def dome(dynamic_config_server, config_port):
    set_config('dome', {
        'brand': 'Simulacrum',
        'driver': 'simulator',
    }, port=config_port)

    the_dome = create_dome_simulator(config_port=config_port)

    yield the_dome

    the_dome.disconnect()


def test_create(dome):
    assert isinstance(dome, simulator.Dome)
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
    assert 'open' in dome.status['open']
    assert dome.is_open is True

    assert dome.close() is True
    assert 'closed' in dome.status['open']
    assert dome.is_closed is True

    assert dome.disconnect() is True
