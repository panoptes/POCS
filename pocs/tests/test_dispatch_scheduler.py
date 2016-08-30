import pytest
import yaml

from astropy import units as u
from astropy.coordinates import EarthLocation
from astropy.time import Time

from astroplan import Observer

from pocs.scheduler.dispatch import Scheduler
from pocs.utils.config import load_config

from pocs.scheduler.constraint import Duration
from pocs.scheduler.constraint import MoonAvoidance

config = load_config()

# Simple constraint to maximize duration above a certain altitude
constraints = [MoonAvoidance(), Duration(30 * u.deg)]

simple_fields_file = config['directories']['targets'] + '/simple.yaml'
loc = config['location']
location = EarthLocation(lon=loc['longitude'], lat=loc['latitude'], height=loc['elevation'])
observer = Observer(location=location, name="Test Observer", timezone=loc['timezone'])


@pytest.fixture
def scheduler():
    field_list = yaml.load("""
    -
        name: HD 189733
        position: 20h00m43.7135s +22d42m39.0645s
        priority: 100
    -
        name: HD 209458
        position: 22h03m10.7721s +18d53m03.543s
        priority: 100
    -
        name: Tres 3
        position: 17h52m07.02s +37d32m46.2012s
        priority: 100
        exp_set_size: 15
        min_nexp: 240
    -
        name: M5
        position: 15h18m33.2201s +02d04m51.7008s
        priority: 50
    -
        name: KIC 8462852
        position: 20h06m15.4536s +44d27m24.75s
        priority: 50
        exp_time: 60
        exp_set_size: 15
        min_nexp: 45
    -
        name: Wasp 33
        position: 02h26m51.0582s +37d33m01.733s
        priority: 100
    -
        name: M42
        position: 05h35m17.2992s -05d23m27.996s
        priority: 25
        exp_time: 240
    -
        name: M44
        position: 08h40m24s +19d40m00.12s
        priority: 50
    """)
    return Scheduler(observer, fields_list=field_list, constraints=constraints)


def test_scheduler_load_no_params():
    with pytest.raises(TypeError):
        Scheduler()


def test_no_observer():
    with pytest.raises(TypeError):
        Scheduler(fields_file=simple_fields_file)


def test_bad_observer():
    with pytest.raises(TypeError):
        Scheduler(fields_file=simple_fields_file, constraints=constraints)


def test_loading_target_file():
    scheduler = Scheduler(observer, fields_file=simple_fields_file, constraints=constraints)
    assert scheduler.observations is not None


def test_with_location(scheduler):
    assert isinstance(scheduler, Scheduler)


def test_loading_bad_target_file():
    with pytest.raises(FileNotFoundError):
        Scheduler(observer, fields_file='/var/path/foo.bar')


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


def test_get_observation(scheduler):
    time = Time('2016-08-13 10:00:00')

    best = scheduler.get_observation(time=time)

    assert best[0] == 'HD 189733'
    assert type(best[1]) == float


def test_observation_seq_time(scheduler):
    time = Time('2016-08-13 10:00:00')

    scheduler.get_observation(time=time)

    assert scheduler.current_observation.seq_time is not None


def test_set_observation_then_reset(scheduler):
    time = Time('2016-08-13 05:00:00')
    scheduler.get_observation(time=time)

    obs1 = scheduler.current_observation
    original_seq_time = obs1.seq_time

    # Reset priority
    scheduler.observations[obs1.name].priority = 1.0

    scheduler.get_observation(time=time)
    obs2 = scheduler.current_observation

    assert obs1 != obs2

    scheduler.observations[obs1.name].priority = 500.0

    scheduler.get_observation(time=time)
    obs3 = scheduler.current_observation
    obs3_seq_time = obs3.seq_time

    assert original_seq_time != obs3_seq_time

    # Now reselect same target and test that seq_time does not change
    scheduler.get_observation(time=time)
    obs4 = scheduler.current_observation
    assert obs4.seq_time == obs3_seq_time
