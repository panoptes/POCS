import pytest

from astropy import units as u

from panoptes.pocs.scheduler.field import Field
from panoptes.pocs.scheduler.observation import Observation


@pytest.fixture
def field(dynamic_config_server, config_port):
    return Field('Test Observation', '20h00m43.7135s +22d42m39.0645s', config_port=config_port)


def test_create_observation_no_field(dynamic_config_server, config_port):
    with pytest.raises(TypeError):
        Observation(config_port=config_port)


def test_create_observation_bad_field(dynamic_config_server, config_port):
    with pytest.raises(AssertionError):
        Observation('20h00m43.7135s +22d42m39.0645s', config_port=config_port)


def test_create_observation_exptime_no_units(dynamic_config_server, config_port, field):
    with pytest.raises(TypeError):
        Observation(field, exptime=1.0, config_port=config_port)


def test_create_observation_exptime_bad(dynamic_config_server, config_port, field):
    with pytest.raises(AssertionError):
        Observation(field, exptime=0.0 * u.second, config_port=config_port)


def test_create_observation_exptime_minutes(dynamic_config_server, config_port, field):
    obs = Observation(field, exptime=5.0 * u.minute, config_port=config_port)
    assert obs.exptime == 300 * u.second


def test_bad_priority(dynamic_config_server, config_port, field):
    with pytest.raises(AssertionError):
        Observation(field, priority=-1, config_port=config_port)


def test_good_priority(dynamic_config_server, config_port, field):
    obs = Observation(field, priority=5.0, config_port=config_port)
    assert obs.priority == 5.0


def test_priority_str(dynamic_config_server, config_port, field):
    obs = Observation(field, priority="5", config_port=config_port)
    assert obs.priority == 5.0


def test_bad_min_set_combo(dynamic_config_server, config_port, field):
    with pytest.raises(AssertionError):
        Observation(field, exp_set_size=7, config_port=config_port)
    with pytest.raises(AssertionError):
        Observation(field, min_nexp=57, config_port=config_port)


def test_small_sets(dynamic_config_server, config_port, field):
    obs = Observation(field, exptime=1 * u.second, min_nexp=1,
                      exp_set_size=1, config_port=config_port)
    assert obs.minimum_duration == 1 * u.second
    assert obs.set_duration == 1 * u.second


def test_good_min_set_combo(dynamic_config_server, config_port, field):
    obs = Observation(field, min_nexp=21, exp_set_size=3, config_port=config_port)
    assert isinstance(obs, Observation)


def test_default_min_duration(dynamic_config_server, config_port, field):
    obs = Observation(field, config_port=config_port)
    assert obs.minimum_duration == 7200 * u.second


def test_default_set_duration(dynamic_config_server, config_port, field):
    obs = Observation(field, config_port=config_port)
    assert obs.set_duration == 1200 * u.second


def test_print(dynamic_config_server, config_port, field):
    obs = Observation(field, exptime=17.5 * u.second, min_nexp=27,
                      exp_set_size=9, config_port=config_port)
    test_str = "Test Observation: 17.5 s exposures in blocks of 9, minimum 27, priority 100"
    assert str(obs) == test_str


def test_seq_time(dynamic_config_server, config_port, field):
    obs = Observation(field, exptime=17.5 * u.second, min_nexp=27,
                      exp_set_size=9, config_port=config_port)
    assert obs.seq_time is None


def test_no_exposures(dynamic_config_server, config_port, field):
    obs = Observation(field, exptime=17.5 * u.second, min_nexp=27,
                      exp_set_size=9, config_port=config_port)
    assert obs.first_exposure is None
    assert obs.last_exposure is None
    assert obs.pointing_image is None


def test_last_exposure_and_reset(dynamic_config_server, config_port, field):
    obs = Observation(field, exptime=17.5 * u.second, min_nexp=27,
                      exp_set_size=9, config_port=config_port)
    status = obs.status
    assert status['current_exp'] == obs.current_exp_num

    # Mimic taking exposures
    obs.merit = 112.5

    for i in range(5):
        obs.exposure_list[f'image_{i}'] = f'full_image_path_{i}'

    last = obs.last_exposure
    assert isinstance(last, tuple)
    assert obs.merit > 0.0
    assert obs.current_exp_num == 5

    assert last[0] == 'image_4'
    assert last[1] == 'full_image_path_4'

    assert isinstance(obs.first_exposure, tuple)
    assert obs.first_exposure[0] == 'image_0'
    assert obs.first_exposure[1] == 'full_image_path_0'

    obs.reset()
    status2 = obs.status

    assert status2['current_exp'] == 0
    assert status2['merit'] == 0.0
    assert obs.first_exposure is None
    assert obs.last_exposure is None
    assert obs.seq_time is None
