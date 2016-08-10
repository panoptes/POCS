import pytest

import astropy.units as u

from pocs.observatory import Observatory

obs = None


@pytest.fixture
def obs():
    """ Return a valid Observatory instance """
    return Observatory(simulator=['mount', 'weather', 'camera'])


def test_default_config(obs):
    """ Creates a default Observatory and tests some of the basic parameters """

    assert obs.location is not None
    assert obs.location.get('elevation') - obs.config['location']['elevation'] < 1. * u.meter
    assert obs.location.get('horizon') == obs.config['location']['horizon']
