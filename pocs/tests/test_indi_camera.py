import pytest

from ..camera import canon_indi
from ..utils.config import load_config

config = load_config()

camera = None


def test_loading_without_config():
    """ Tests the basic loading of a mount """
    with pytest.raises(TypeError):
        camera = canon_indi.Camera()

        assert camera.is_connected, "Camera not connected"


def test_simple():
    """ Tests the basic loading of a canon camera """
    camera = canon_indi.Camera({'name': 'Cam00', 'port': 'usb:001,004'})

    assert camera.name is not None, "Can't get name from camera."

# def test_default():
#     """ Creates a simply client, which will try to connect to the server """
#     client = indi.PanIndi()
#
#     assert client.devices is not None
