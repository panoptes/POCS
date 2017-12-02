import copy
import os
import pytest

from pocs.dome import CreateDomeFromConfig
from pocs.dome.simulator import Dome as DomeSimulator


# Yields two different dome controllers configurations,
# both with the pocs.dome.simulator.Dome class, but one
# overriding the specified driver with the simulator,
# the other explicitly specified.
@pytest.fixture(scope="function", params=[False, True])
def dome(request, config):
    config = copy.deepcopy(config)
    is_simulator = request.param
    if is_simulator:
        config.update({
            'dome': {
                'brand': 'Astrohaven',
                'driver': 'astrohaven',
            },
            'simulator': ['something', 'dome', 'another'],
        })
    else:
        config.update({
            'dome': {
                'brand': 'Simulacrum',
                'driver': 'simulator',
            },
        })
        del config['simulator']
    the_dome = CreateDomeFromConfig(config)
    yield the_dome
    if is_simulator:
        # Should have marked the dome as being simulated.
        assert config['dome']['simulator']
    else:
        # Doesn't know that a simulator was specified.
        assert 'simulator' not in config['dome']
    the_dome.disconnect()


def test_create(dome):
    assert isinstance(dome, DomeSimulator)
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
