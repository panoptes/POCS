import os
import pytest


from pocs.dome.bisque import Dome
from pocs.utils.theskyx import TheSkyX

pytestmark = pytest.mark.skipif(TheSkyX().is_connected is False,
                                reason="TheSkyX is not connected")


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


def test_connect(dome):
    assert dome.connect() is True
    assert dome.is_connected is True


def test_disconnect(dome):
    assert dome.connect() is True
    assert dome.disconnect() is True
    assert dome.is_connected is False


def test_open_and_close_slit(dome):
    dome.connect()

    assert dome.open_slit() is True
    # assert dome.slit_state == 'Open'
    assert dome.is_open is True

    assert dome.close_slit() is True
    # assert dome.slit_state == 'Closed'
    assert dome.is_closed is True
