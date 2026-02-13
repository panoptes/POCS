from pathlib import Path

import pytest
from astropy import units as u

from panoptes.pocs.scheduler.field import Field
from panoptes.pocs.scheduler.observation.base import Exposure, Observation


@pytest.fixture
def field():
    return Field("Test Observation", "20h00m43.7135s +22d42m39.0645s")


def test_create_observation_no_field():
    with pytest.raises(TypeError):
        Observation()


def test_create_observation_bad_field():
    with pytest.raises(TypeError):
        Observation("20h00m43.7135s +22d42m39.0645s")


def test_create_observation_exptime_bad(field):
    with pytest.raises(ValueError):
        Observation(field, exptime=-1.0 * u.second)


def test_create_observation_exptime_minutes(field):
    obs = Observation(field, exptime=5.0 * u.minute)
    assert obs.exptime == 300 * u.second


def test_bad_priority(field):
    with pytest.raises(ValueError):
        Observation(field, priority=-1)


def test_good_priority(field):
    obs = Observation(field, priority=5.0)
    assert obs.priority == 5.0


def test_priority_str(field):
    obs = Observation(field, priority="5")
    assert obs.priority == 5.0


def test_bad_min_set_combo(field):
    with pytest.raises(ValueError):
        Observation(field, exp_set_size=7)
    with pytest.raises(ValueError):
        Observation(field, min_nexp=57)


def test_small_sets(field):
    obs = Observation(field, exptime=1 * u.second, min_nexp=1, exp_set_size=1)
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
    obs = Observation(field, exptime=17.5 * u.second, min_nexp=27, exp_set_size=9)
    test_str = "Test Observation: 17.5 s exposures in blocks of 9, minimum 27, priority 100"
    assert str(obs) == test_str


def test_seq_time(field):
    obs = Observation(field, exptime=17.5 * u.second, min_nexp=27, exp_set_size=9)
    assert obs.seq_time is None


def test_no_exposures(field):
    obs = Observation(field, exptime=17.5 * u.second, min_nexp=27, exp_set_size=9)
    assert obs.first_exposure == list()
    assert obs.last_exposure == list()
    assert obs.pointing_image is None


def test_last_exposure_and_reset(field):
    obs = Observation(field, exptime=17.5 * u.second, min_nexp=27, exp_set_size=9)
    status = obs.status
    assert status["current_exp"] == obs.current_exp_num

    # Mimic taking exposures
    obs.merit = 112.5

    for i in range(5):
        obs.add_to_exposure_list(
            "Cam00", Exposure(image_id=f"image_{i}", path=f"full_image_path_{i}", metadata=dict())
        )

    last = obs.last_exposure
    assert isinstance(last, list)
    assert isinstance(last[0]["Cam00"], Exposure)
    assert obs.merit > 0.0
    assert obs.current_exp_num == 5

    assert isinstance(obs.first_exposure, list)
    assert obs.first_exposure[0]["Cam00"].image_id == "image_0"
    assert obs.first_exposure[0]["Cam00"].path == Path("full_image_path_0")

    obs.reset()
    status2 = obs.status

    assert status2["current_exp"] == 0
    assert status2["merit"] == 0.0
    assert obs.first_exposure == list()
    assert obs.last_exposure == list()
    assert obs.seq_time is None


def test_observation_tags(field):
    """Test that tags are properly stored and serialized."""
    tags = ["exoplanet", "test_tag", "bright_star"]
    obs = Observation(field, tags=tags)
    
    # Test tags are stored
    assert obs.tags == tags
    
    # Test tags in status
    status = obs.status
    assert "tags" in status
    assert status["tags"] == tags
    
    # Test tags in to_dict
    obs_dict = obs.to_dict()
    assert "tags" in obs_dict
    assert obs_dict["tags"] == tags


def test_observation_no_tags(field):
    """Test observation without tags defaults to empty list."""
    obs = Observation(field)
    
    # Test default is empty list
    assert obs.tags == []
    
    # Test tags in status
    status = obs.status
    assert "tags" in status
    assert status["tags"] == []
    
    # Test tags in to_dict
    obs_dict = obs.to_dict()
    assert "tags" in obs_dict
    assert obs_dict["tags"] == []


def test_observation_from_dict_with_tags():
    """Test creating observation from dict with tags."""
    observation_config = {
        "field": {
            "name": "Test Field",
            "position": "20h00m43.7135s +22d42m39.0645s"
        },
        "observation": {
            "priority": 100,
            "exptime": 30,
            "tags": ["exoplanet", "defocus_test"]
        }
    }
    
    obs = Observation.from_dict(observation_config)
    assert obs.tags == ["exoplanet", "defocus_test"]
    assert obs.priority == 100
    assert obs.exptime == 30 * u.second


def test_observation_from_dict_without_tags():
    """Test creating observation from dict without tags."""
    observation_config = {
        "field": {
            "name": "Test Field",
            "position": "20h00m43.7135s +22d42m39.0645s"
        },
        "observation": {
            "priority": 100,
            "exptime": 30
        }
    }
    
    obs = Observation.from_dict(observation_config)
    assert obs.tags == []
    assert obs.priority == 100
