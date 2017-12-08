# Test the Astrohaven dome interface using a simulated dome controller.

import copy
import pytest
import serial

from pocs.dome import CreateDomeFromConfig
from pocs.dome import astrohaven


@pytest.fixture(scope='function')
def dome(config):
    # Install our test handlers for the duration.
    serial.protocol_handler_packages.append('pocs.dome')

    # Modify the config so that the dome uses the right controller and port.
    config = copy.deepcopy(config)
    dome_config = config.setdefault('dome', {})
    dome_config.update({
        'brand': 'Astrohaven',
        'driver': 'astrohaven',
        'port': 'astrohaven_simulator://',
    })
#    config.update({
#        'dome': {
#            'brand': 'Astrohaven',
#            'driver': 'astrohaven',
#            'port': 'astrohaven_simulator://',
#        },
#    })
    del config['simulator']
    the_dome = CreateDomeFromConfig(config)
    yield the_dome

    # Remove our test handlers.
    serial.protocol_handler_packages.remove('pocs.dome')


def test_create(dome):
    pytest.set_trace()
    assert isinstance(dome, astrohaven.AstrohavenDome)
    assert isinstance(dome, astrohaven.Dome)
    # We use rs232.SerialData, which automatically connects.
    assert dome.is_connected


def test_connect_and_disconnect(dome):
    # We use rs232.SerialData, which automatically connects.
    assert dome.is_connected is True
    assert dome.disconnect() is True
    assert dome.is_connected is False
    assert dome.connect() is True
    assert dome.is_connected is True
    assert dome.disconnect() is True
    assert dome.is_connected is False


def test_diXXXsconnect(dome):
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
