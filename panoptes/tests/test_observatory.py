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
