import pytest

from ...utils import indi as indi
import astropy.units as u

from ...camera import canon_indi
from ...utils.config import load_config

config = load_config()

camera = None


def test_loading_without_config():
    """ Tests the basic loading of a mount """
    with pytest.raises(TypeError):
        camera = canon_indi.Camera()


def test_simple():
    """ Tests the basic loading of a canon camera """
    camera = canon_indi.Camera('GPhoto CCD', config={'port': 'usb:001,004'})

    assert camera.serial_number is not None, self.logger.warning("Can't get serial number from camera.")

# def test_default():
#     """ Creates a simply client, which will try to connect to the server """
#     client = indi.PanIndi()
#
#     assert client.devices is not None
