import pytest

from astropy import units as u
from astropy.coordinates import EarthLocation

from astroplan import Observer, Schedule

from astroplan import (AltitudeConstraint, AirmassConstraint, AtNightConstraint)

from pocs.scheduler.dispatch import Scheduler
from pocs.utils.config import load_config

config = load_config()

constraints = [AltitudeConstraint(30 * u.deg),
               AirmassConstraint(5),
               AtNightConstraint.twilight_civil()]

simple_fields_file = config['directories']['targets'] + '/simple.yaml'
loc = config['location']
location = EarthLocation(lon=loc['longitude'], lat=loc['latitude'], height=loc['elevation'])


@pytest.fixture
def scheduler():
    return Scheduler(simple_fields_file)


def test_scheduler_load_no_params():
    with pytest.raises(TypeError):
        Scheduler()


def test_with_location(scheduler):
    assert isinstance(scheduler, Scheduler)


def test_loading_target_file(scheduler):
    assert scheduler.observations is not None


def test_loading_bad_target_file():
    with pytest.raises(AssertionError):
        Scheduler('/var/path/foo.bar')


def test_scheduler_add_field(scheduler):
    orig_length = len(scheduler.observations)

    scheduler.add_observation({
        'name': 'Degree Field',
        'position': '12h30m01s +08d08m08s',
    })

    assert len(scheduler.observations) == orig_length + 1


def test_scheduler_add_duplicate_field(scheduler):

    scheduler.add_observation({
        'name': 'Duplicate Field',
        'position': '12h30m01s +08d08m08s',
    })

    with pytest.raises(AssertionError):
        scheduler.add_observation({
            'name': 'Duplicate Field',
            'position': '12h30m01s +08d08m08s',
        })


def test_scheduler_add_duplicate_field_different_name(scheduler):
    orig_length = len(scheduler.observations)

    scheduler.add_observation({
        'name': 'Duplicate Field',
        'position': '12h30m01s +08d08m08s',
    })

    scheduler.add_observation({
        'name': 'Duplicate Field 2',
        'position': '12h30m01s +08d08m08s',
    })

    assert len(scheduler.observations) == orig_length + 2


def test_scheduler_add_with_exp_time(scheduler):
    orig_length = len(scheduler.observations)

    scheduler.add_observation({
        'name': 'Added Field',
        'position': '12h30m01s +08d08m08s',
        'exp_time': '60'
    })

    assert len(scheduler.observations) == orig_length + 1
    assert scheduler.observations['Added Field'].exp_time == 60 * u.second


def test_remove_field(scheduler):
    orig_keys = list(scheduler.observations.keys())
    scheduler.remove_observation('HD 189733')
    assert orig_keys != scheduler.observations.keys()
