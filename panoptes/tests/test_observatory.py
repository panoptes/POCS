import pytest

import astropy.units as u

from ..observatory import Observatory
from ..utils.config import load_config

config = load_config()

obs = None


def test_no_config():
    """ Creates a blank Observatory with no config, which should fail """
    with pytest.raises(AssertionError):
        obs = Observatory()

def test_default_config():
    """ Creates a default Observatory and tests some of the basic parameters """
    obs = Observatory(config=config)

    assert obs.location is not None
    assert obs.location.get('elevation') - config['location']['elevation'] * u.meter < 1. * u.meter
    assert obs.location.get('horizon') == config['location']['horizon'] * u.degree

class TestObservatory:
    def __init__(self):
        self.observatory = Observatory(config=config)

    def test_ha_dec_failure_01(self):
        """ Tests ha_dec requires commands """

        with pytest.raises(AssertionError):
            self.observatory.scheduler.get_coords_for_ha_dec()

    def test_ha_dec_failure_02(self):

        with pytest.raises(AssertionError):
            self.observatory.scheduler.get_coords_for_ha_dec(ha=-170 * u.degree)

    def test_ha_dec_failure_03(self):

        with pytest.raises(AssertionError):
            self.observatory.scheduler.get_coords_for_ha_dec(dec=-10 * u.degree)

    def test_ha_dec_failure_04(self):

        with pytest.raises(AssertionError):
            self.observatory.scheduler.get_coords_for_ha_dec(ha=-170, dec=-10 * u.degree)
