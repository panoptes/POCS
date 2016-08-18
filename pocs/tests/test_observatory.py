import os
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


def test_is_dark(observatory):
    os.environ['POCSTIME'] = '2016-08-13 10:00:00'
    assert observatory.is_dark is True

    os.environ['POCSTIME'] = '2016-08-13 22:00:00'
    assert observatory.is_dark is False


def test_sidereal_time(observatory):
    os.environ['POCSTIME'] = '2016-08-13 10:00:00'
    st = observatory.sidereal_time
    assert st.value == 21.11269263733713

    os.environ['POCSTIME'] = '2016-08-13 22:00:00'
    st = observatory.sidereal_time
    assert st.value == 9.145547849536634


def test_primary_camera(observatory):
    assert observatory.primary_camera is not None


def test_get_observation(observatory):
    start_of_night = observatory.observer.tonight()[0]
    observation = observatory.get_observation(time=start_of_night)
    assert isinstance(observation, Observation)

    assert observatory.current_observation == observation
