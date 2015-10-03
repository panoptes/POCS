import pytest

import astropy.units as u

from ..utils import load_config, has_logger
from ..utils.indi import PanIndiServer, PanIndiDevice

@has_logger
class TestIndi(object):
    """ Class for testing INDI modules s"""
    def __init__(self):
        self.logger.debug("Testig INDI")
        config = load_config()

    def test_no_config():
        """ Creates a blank Observatory with no config, which should fail """
        # with pytest.raises(AssertionError):
        indi_server = PanIndiServer()
