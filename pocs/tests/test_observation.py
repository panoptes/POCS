import pytest

from astropy import units as u
from pocs.scheduler.observation import Observation


def test_create_observation_no_params():
    with pytest.raises(TypeError):
        Observation()


def test_create_observation_bad_position():
    with pytest.raises(ValueError):
        Observation("TestObservation", "Bad Position")


def test_create_observation_bad_priority():
    with pytest.raises(AssertionError):
        Observation('TestObservation', '20h00m43.7135s +22d42m39.0645s', priority=0)
        Observation('TestObservation', '20h00m43.7135s +22d42m39.0645s', priority=-1)


def test_create_observation_exp_time_no_units():
    with pytest.raises(TypeError):
        Observation('TestObservation', '20h00m43.7135s +22d42m39.0645s', exp_time=1.0)


def test_create_observation_exp_time_bad():
    with pytest.raises(AssertionError):
        Observation(
            'TestObservation',
            '20h00m43.7135s +22d42m39.0645s',
            exp_time=0.0 * u.second,
        )


def test_create_observation_exp_time_minutes():
    observation = Observation(
        'TestObservation',
        '20h00m43.7135s +22d42m39.0645s',
        exp_time=5.0 * u.minute,
    )
    assert observation.exp_time == 300 * u.second


def test_create_observation_default_duration():
    observation = Observation(
        'TestObservation',
        '20h00m43.7135s +22d42m39.0645s',
    )
    assert observation.duration == 7200 * u.second


def test_create_observation_good_priority():
    observation = Observation('TestObservation', '20h00m43.7135s +22d42m39.0645s', priority=5.0)
    assert observation.priority == 5.0


def test_create_observation_priority_str():
    observation = Observation('TestObservation', '20h00m43.7135s +22d42m39.0645s', priority="5")
    assert observation.priority == 5.0


def test_create_observation_name():
    observation = Observation('Test Observation - 32b', '20h00m43.7135s +22d42m39.0645s')
    assert observation.name == 'Test Observation - 32b'


def test_create_observation_Observation_name():
    observation = Observation('Test Observation - 32b', '20h00m43.7135s +22d42m39.0645s')
    assert observation.Observation_name == 'TestObservation32B'
