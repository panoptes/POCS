import os
import pytest

from panoptes.pocs.dome.bisque import Dome
from panoptes.utils.theskyx import TheSkyX

pytestmark = pytest.mark.skipif(TheSkyX().is_connected is False, reason="TheSkyX is not connected")


@pytest.fixture(scope="function")
def dome(config):
    try:
        del os.environ['POCSTIME']
    except KeyError:
        pass

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


def test_disconnect(dome):
    assert dome.connect() is True
    assert dome.disconnect() is True
    assert dome.is_connected is False


def test_open_and_close_slit(dome):
    dome.connect()

    assert dome.open() is True
    assert dome.read_slit_state() == 'Open'
    assert dome.status == 'Open'
    assert dome.is_open is True

    assert dome.close() is True
    assert dome.read_slit_state() == 'Closed'
    assert dome.status == 'Closed'
    assert dome.is_closed is True

    assert dome.disconnect() is True
