import pytest

from ..utils import indi as indi
import astropy.units as u

from ...camera import canon
from ...utils.config import load_config

config = load_config()

camera = None

def test_simple():
    """ Tests the basic loading of a canon camera """
    camera = canon.Camera()

def test_default():
    """ Creates a simply client, which will try to connect to the server """
    client = indi.PanIndi()

    assert client.devices is not None
