import pytest

from pocs.dome import simulator
from pocs.dome import create_dome_simulator

from panoptes.utils.config.client import get_config
from panoptes.utils.config.client import set_config


# Yields two different dome controllers configurations,
# both with the pocs.dome.simulator.Dome class, but one
# overriding the specified driver with the simulator,
# the other explicitly specified.
@pytest.fixture(scope="function", params=[False, True])
def dome(request, dynamic_config_server, config_port):
    is_simulator = request.param
    if is_simulator:
        set_config('dome', {
            'brand': 'Astrohaven',
            'driver': 'astrohaven',
        }, port=config_port)
        set_config('simulator', ['something', 'dome', 'another'], port=config_port)
    else:
        set_config('dome', {
            'brand': 'Simulacrum',
            'driver': 'simulator',
        }, port=config_port)
        # del config['simulator']

    the_dome = create_dome_simulator(config_port=config_port)

    yield the_dome

    if is_simulator:
        # Should have marked the dome as being simulated.
        assert 'dome' in get_config('simulator')
    else:
        # Doesn't know that a simulator was specified.
        assert get_config('dome.simulator') is None
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
    assert 'open' in dome.status.lower()
    assert dome.is_open is True

    assert dome.close() is True
    assert 'closed' in dome.status.lower()
    assert dome.is_closed is True

    assert dome.disconnect() is True
