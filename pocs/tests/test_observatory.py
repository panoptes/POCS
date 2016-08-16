import pytest

import astropy.units as u

from pocs.observatory import Observatory
from pocs.scheduler.dispatch import Scheduler
from pocs.scheduler.observation import Observation

obs = None


@pytest.fixture
def observatory():
    """ Return a valid Observatory instance """
    return Observatory(simulator=['mount', 'weather', 'camera'])


def test_default_config(observatory):
    """ Creates a default Observatory and tests some of the basic parameters """

    assert observatory.location is not None
    assert observatory.location.get('elevation') - observatory.config['location']['elevation'] < 1. * u.meter
    assert observatory.location.get('horizon') == observatory.config['location']['horizon']
    assert hasattr(observatory, 'scheduler')
    assert isinstance(observatory.scheduler, Scheduler)


def test_get_observation(observatory):
    observation = observatory.get_observation()
    assert isinstance(observation, Observation)
