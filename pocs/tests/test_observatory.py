import os
import pytest

import astropy.units as u

from pocs.observatory import Observatory
from pocs.scheduler.dispatch import Scheduler
from pocs.scheduler.observation import Observation


@pytest.fixture
def simulator(request):
    sim = list()

    if not request.config.getoption("--camera"):
        sim.append('camera')

    if not request.config.getoption("--mount"):
        sim.append('mount')

    if not request.config.getoption("--weather"):
        sim.append('weather')

    return sim

noobserve = pytest.mark.skipif(
    not pytest.config.getoption("--camera"),
    reason="need --camera to observe"
)


@pytest.fixture
def observatory(simulator):
    """ Return a valid Observatory instance """
    return Observatory(simulator=simulator)


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
    assert abs(st.value - 21.11269263733713) < 1e-4

    os.environ['POCSTIME'] = '2016-08-13 22:00:00'
    st = observatory.sidereal_time
    assert abs(st.value - 9.145547849536634) < 1e-4


def test_primary_camera(observatory):
    assert observatory.primary_camera is not None


def test_get_observation(observatory):
    start_of_night = observatory.observer.tonight()[0]
    observation = observatory.get_observation(time=start_of_night)
    assert isinstance(observation, Observation)

    assert observatory.current_observation == observation


@noobserve
def test_observe(observatory):
    assert observatory.current_observation is None
    observatory.get_observation()
    assert observatory.current_observation is not None

    assert observatory.current_observation.current_exp == 0
    observatory.observe()
    assert observatory.current_observation.current_exp == 1
