import os
import yaml
import pytest

from astropy import units as u
from astropy.coordinates import EarthLocation
from astropy.time import Time
from astroplan import Observer

from panoptes.pocs.scheduler.dispatch import Scheduler
from panoptes.pocs.scheduler.constraint import Duration
from panoptes.pocs.scheduler.constraint import MoonAvoidance

from panoptes.utils.config.client import get_config


@pytest.fixture
def constraints(dynamic_config_server, config_port):
    return [MoonAvoidance(config_port=config_port), Duration(30 * u.deg, config_port=config_port)]


@pytest.fixture
def observer(dynamic_config_server, config_port):
    loc = get_config('location', port=config_port)
    location = EarthLocation(lon=loc['longitude'], lat=loc['latitude'], height=loc['elevation'])
    return Observer(location=location, name="Test Observer", timezone=loc['timezone'])


@pytest.fixture()
def field_file(dynamic_config_server, config_port):
    scheduler_config = get_config('scheduler', default={}, port=config_port)

    # Read the targets from the file
    fields_file = scheduler_config.get('fields_file', 'simple.yaml')
    fields_path = os.path.join(get_config('directories.targets', port=config_port), fields_file)

    return fields_path


@pytest.fixture()
def field_list():
    return yaml.full_load("""
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
        exptime: 60
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
        exptime: 240
    -
        name: M44
        position: 08h40m24s +19d40m00.12s
        priority: 50
    """)


@pytest.fixture
def scheduler(dynamic_config_server, config_port, field_list, observer, constraints):
    return Scheduler(observer,
                     fields_list=field_list,
                     constraints=constraints,
                     config_port=config_port)


@pytest.fixture
def scheduler_from_file(dynamic_config_server, config_port, field_file, observer, constraints):
    return Scheduler(observer,
                     fields_file=field_file,
                     constraints=constraints,
                     config_port=config_port)


@pytest.fixture
def scheduler_from_file(field_file, observer, constraints):
    return Scheduler(observer, fields_file=field_file, constraints=constraints)


def test_get_observation(scheduler):
    time = Time('2016-08-13 10:00:00')

    best = scheduler.get_observation(time=time)

    assert best[0] == 'HD 189733'
    assert isinstance(best[1], float)


def test_get_observation_reread(dynamic_config_server,
                                config_port,
                                field_list,
                                observer,
                                temp_file,
                                constraints):
    time = Time('2016-08-13 10:00:00')

    # Write out the field list
    with open(temp_file, 'w') as f:
        f.write(yaml.dump(field_list))

    scheduler = Scheduler(observer,
                          fields_file=temp_file,
                          constraints=constraints,
                          config_port=config_port)

    # Get observation as above
    best = scheduler.get_observation(time=time)
    assert best[0] == 'HD 189733'

    # Alter the field file - note same target but new name
    with open(temp_file, 'a') as f:
        f.write(yaml.dump([{
            'name': 'New Name',
            'position': '20h00m43.7135s +22d42m39.0645s',
            'priority': 5000
        }]))

    # Get observation but reread file first
    best = scheduler.get_observation(time=time, reread_fields_file=True)
    assert best[0] != 'HD 189733'


def test_observation_seq_time(scheduler):
    time = Time('2016-08-13 10:00:00')

    scheduler.get_observation(time=time)

    assert scheduler.current_observation.seq_time is not None


def test_no_valid_observation(scheduler):
    time = Time('2016-08-13 15:00:00')
    scheduler.get_observation(time=time)
    assert scheduler.current_observation is None


def test_continue_observation(scheduler):
    time = Time('2016-08-13 11:00:00')
    scheduler.get_observation(time=time)
    assert scheduler.current_observation is not None
    obs = scheduler.current_observation

    time = Time('2016-08-13 13:00:00')
    scheduler.get_observation(time=time)
    assert scheduler.current_observation == obs

    time = Time('2016-08-13 14:30:00')
    scheduler.get_observation(time=time)
    assert scheduler.current_observation is None


def test_set_observation_then_reset(scheduler):
    try:
        del os.environ['POCSTIME']
    except Exception:
        pass

    time = Time('2016-08-13 05:00:00')
    scheduler.get_observation(time=time)

    obs1 = scheduler.current_observation
    original_seq_time = obs1.seq_time

    # Reset priority
    scheduler.observations[obs1.name].priority = 1.0

    time = Time('2016-08-13 05:30:00')
    scheduler.get_observation(time=time)
    obs2 = scheduler.current_observation

    assert obs1 != obs2

    scheduler.observations[obs1.name].priority = 500.0

    time = Time('2016-08-13 06:00:00')
    scheduler.get_observation(time=time)
    obs3 = scheduler.current_observation
    obs3_seq_time = obs3.seq_time

    assert original_seq_time != obs3_seq_time

    # Now reselect same target and test that seq_time does not change
    scheduler.get_observation(time=time)
    obs4 = scheduler.current_observation
    assert obs4.seq_time == obs3_seq_time


def test_reset_observation(scheduler):
    time = Time('2016-08-13 05:00:00')
    scheduler.get_observation(time=time)

    # We have an observation so we have a seq_time
    assert scheduler.current_observation.seq_time is not None

    obs = scheduler.current_observation

    # Trigger a reset
    scheduler.current_observation = None

    assert obs.seq_time is None


def test_new_observation_seq_time(scheduler):
    time = Time('2016-09-11 07:08:00')
    scheduler.get_observation(time=time)

    # We have an observation so we have a seq_time
    assert scheduler.current_observation.seq_time is not None

    # A few hours later
    time = Time('2016-09-11 10:30:00')
    scheduler.get_observation(time=time)

    assert scheduler.current_observation.seq_time is not None


def test_observed_list(scheduler):
    assert len(scheduler.observed_list) == 0

    time = Time('2016-09-11 07:08:00')
    scheduler.get_observation(time=time)

    assert len(scheduler.observed_list) == 1

    # A few hours later should now be different
    time = Time('2016-09-11 10:30:00')
    scheduler.get_observation(time=time)

    assert len(scheduler.observed_list) == 2

    # A few hours later should be the same
    time = Time('2016-09-11 14:30:00')
    scheduler.get_observation(time=time)

    assert len(scheduler.observed_list) == 2

    scheduler.reset_observed_list()

    assert len(scheduler.observed_list) == 0
