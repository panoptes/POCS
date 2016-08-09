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
    obs = Observer(location=location)
    times = obs.tonight()

    return Scheduler(simple_fields_file,
                     start_time=times[0],
                     end_time=times[1],
                     observer=obs,
                     constraints=constraints)


def test_scheduler_load_no_params():
    with pytest.raises(TypeError):
        Scheduler()


def test_scheduler_load_no_location():
    with pytest.raises(TypeError):
        Scheduler(simple_fields_file)


def test_with_location(scheduler):
    assert isinstance(scheduler, Scheduler)


def test_loading_target_file(scheduler):
    assert scheduler.fields is not None


def test_scheduler_add_field(scheduler):
    orig_length = len(scheduler.fields)

    scheduler.add_field({
        'name': 'Degree Field',
        'position': '12h30m01s +08d08m08s',
    })

    assert len(scheduler.fields) == orig_length + 1


def test_scheduler_add_duplicate_field(scheduler):

    scheduler.add_field({
        'name': 'Duplicate Field',
        'position': '12h30m01s +08d08m08s',
    })

    with pytest.raises(AssertionError):
        scheduler.add_field({
            'name': 'Duplicate Field',
            'position': '12h30m01s +08d08m08s',
        })


def test_scheduler_add_duplicate_field_different_name(scheduler):
    orig_length = len(scheduler.fields)

    scheduler.add_field({
        'name': 'Duplicate Field',
        'position': '12h30m01s +08d08m08s',
    })

    scheduler.add_field({
        'name': 'Duplicate Field 2',
        'position': '12h30m01s +08d08m08s',
    })

    assert len(scheduler.fields) == orig_length + 2


def test_scheduler_add_with_exp_time(scheduler):
    orig_length = len(scheduler.fields)

    scheduler.add_field({
        'name': 'AddedField',
        'position': '12h30m01s +08d08m08s',
        'exp_time': '60'
    })

    assert len(scheduler.fields) == orig_length + 1


def test_remove_field(scheduler):
    orig_keys = list(scheduler.fields.keys())
    scheduler.remove_field('HD 189733')
    assert orig_keys != scheduler.fields.keys()


def test_has_schedule(scheduler):
    assert isinstance(scheduler.schedule, Schedule)


# def test_get_observability_table(scheduler):
    # scheduler.get_observability_table()
