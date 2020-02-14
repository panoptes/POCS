# Test the Astrohaven dome interface using a simulated dome controller.

import pytest
import serial

from pocs import hardware
from pocs.dome import astrohaven
from pocs.dome import create_dome_simulator

from panoptes.utils.config.client import set_config


@pytest.fixture(scope='function')
def dome(dynamic_config_server, config_port):
    # Install our test handlers for the duration.
    serial.protocol_handler_packages.append('pocs.dome')

    # Modify the config so that the dome uses the right controller and port.
    set_config('simulator', hardware.get_all_names(without=['dome']), port=config_port)
    set_config('dome', {
        'brand': 'Astrohaven',
        'driver': 'astrohaven',
        'port': 'astrohaven_simulator://',
    }, port=config_port)
    the_dome = create_dome_simulator(config_port=config_port)

    yield the_dome
    try:
        the_dome.disconnect()
    except Exception:
        pass

    # Remove our test handlers.
    serial.protocol_handler_packages.remove('pocs.dome')


def test_create(dome):
    assert isinstance(dome, astrohaven.AstrohavenDome)
    assert isinstance(dome, astrohaven.Dome)
    # We use rs232.SerialData, which automatically connects.
    assert dome.is_connected


def test_connect_and_disconnect(dome):
    # We use rs232.SerialData, which automatically connects.
    assert dome.is_connected is True
    dome.disconnect()
    assert dome.is_connected is False
    assert dome.connect() is True
    assert dome.is_connected is True
    dome.disconnect()
    assert dome.is_connected is False


def test_disconnect(dome):
    assert dome.connect() is True
    dome.disconnect()
    assert dome.is_connected is False
    # Can repeat.
    dome.disconnect()
    assert dome.is_connected is False


def test_open_and_close_slit(dome):
    dome.connect()

    assert dome.open() is True
    assert dome.status == 'Both sides open'
    assert dome.is_open is True

    # Try to open shutter
    assert dome.open() is True

    assert dome.close() is True
    assert dome.status == 'Both sides closed'
    assert dome.is_closed is True

    # Try to close again
    assert dome.close() is True

    dome.disconnect()
