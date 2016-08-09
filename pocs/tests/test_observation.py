import pytest

from astropy import units as u
from pocs.scheduler.field import Field
from pocs.scheduler.observation import Observation


@pytest.fixture
def field():
    return Field('TestObservation', '20h00m43.7135s +22d42m39.0645s', priority=5.0)


def test_create_observation_no_field():
    with pytest.raises(TypeError):
        Observation()


def test_create_observation_exp_time_no_units(field):
    with pytest.raises(TypeError):
        Observation(field, exp_time=1.0)


def test_create_observation_exp_time_bad(field):
    with pytest.raises(AssertionError):
        Observation(field, exp_time=0.0 * u.second)


def test_create_observation_exp_time_minutes(field):
    obs = Observation(field, exp_time=5.0 * u.minute)
    assert obs.exp_time == 300 * u.second


def test_bad_priority(field):
    with pytest.raises(AssertionError):
        Observation(field, priority=0)
        Observation(field, priority=-1)


def test_good_priority(field):
    obs = Observation(field, priority=5.0)
    assert obs.priority == 5.0


def test_priority_str(field):
    obs = Observation(field, priority="5")
    assert obs.priority == 5.0


def test_bad_min_set_combo(field):
    with pytest.raises(AssertionError):
        Observation(field, exp_set_size=7)
    with pytest.raises(AssertionError):
        Observation(field, min_nexp=57)


def test_small_sets(field):
    obs = Observation(field, exp_time=1 * u.second, min_nexp=1, exp_set_size=1)
    assert obs.minimum_duration == 1 * u.second
    assert obs.set_duration == 1 * u.second


def test_good_min_set_combo(field):
    obs = Observation(field, min_nexp=21, exp_set_size=3)
    assert isinstance(obs, Observation)


def test_default_min_duration(field):
    obs = Observation(field)
    assert obs.minimum_duration == 7200 * u.second


def test_default_set_duration(field):
    obs = Observation(field)
    assert obs.set_duration == 1200 * u.second


def test_print(field):
    obs = Observation(field, exp_time=17.5 * u.second, min_nexp=27, exp_set_size=9)
    assert str(obs) == "TestObservation: 17.5 s exposures in blocks of 9, minimum 27"
