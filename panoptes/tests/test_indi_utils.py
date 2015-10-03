import pytest

import astropy.units as u

from ..utils.config import load_config
from ..utils.indi import PanIndiServer, PanIndiDevice

config = load_config()

obs = None

def test_no_config():
    """ Creates a blank Observatory with no config, which should fail """
    # with pytest.raises(AssertionError):
    indi_server = PanIndiServer()
