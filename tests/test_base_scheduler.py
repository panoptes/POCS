import pytest

from astropy import units as u
from astropy.coordinates import EarthLocation
from astroplan import Observer

from panoptes.utils import error
from panoptes.utils.config.client import get_config
from panoptes.utils.config.client import set_config
from panoptes.pocs.scheduler import BaseScheduler as Scheduler
from panoptes.pocs.scheduler.constraint import Duration
from panoptes.pocs.scheduler.constraint import MoonAvoidance
from panoptes.utils.serializers import from_yaml


@pytest.fixture
def constraints():
    return [MoonAvoidance(), Duration(30 * u.deg)]


@pytest.fixture
def simple_targets_file():
    return get_config('directories.targets') + '/simulator.yaml'


@pytest.fixture
def observer():
    loc = get_config('location')
    location = EarthLocation(lon=loc['longitude'], lat=loc['latitude'], height=loc['elevation'])
    return Observer(location=location, name="Test Observer", timezone=loc['timezone'])


@pytest.fixture()
def targets_list():
    return from_yaml("""
    -
      field:
        name: HD 189733
        position: 20h00m43.7135s +22d42m39.0645s
      observation:
        priority: 100
    -
      field:
        name: HD 209458
        position: 22h03m10.7721s +18d53m03.543s
        priority: 100
      observation:
        priority: 100
    -
      field:
        name: Tres 3
        position: 17h52m07.02s +37d32m46.2012s
      observation:
        priority: 100
        exp_set_size: 15
        min_nexp: 240
    -
      field:
        name: M5
        position: 15h18m33.2201s +02d04m51.7008s
      observation:
        priority: 50
    -
      field:
        name: KIC 8462852
        position: 20h06m15.4536s +44d27m24.75s
      observation:
        priority: 50
        exptime: 60
        exp_set_size: 15
        min_nexp: 45
    -
      field:
        name: Wasp 33
        position: 02h26m51.0582s +37d33m01.733s
      observation:
        priority: 100
    -
      field:
        name: M42
        position: 05h35m17.2992s -05d23m27.996s
      observation:
        priority: 25
        exptime: 240
    -
      field:
        name: M44
        position: 08h40m24s +19d40m00.12s
      observation:
        priority: 50
    """)


@pytest.fixture
def scheduler(targets_list, observer, constraints):
    return Scheduler(observer,
                     targets_list=targets_list,
                     constraints=constraints)


def test_scheduler_load_no_params():
    with pytest.raises(TypeError):
        Scheduler()


def test_no_observer(simple_targets_file):
    with pytest.raises(TypeError):
        Scheduler(targets_file=simple_targets_file)


def test_bad_observer(simple_targets_file, constraints):
    with pytest.raises(TypeError):
        Scheduler(targets_file=simple_targets_file,
                  constraints=constraints)


def test_loading_target_file_check_file(observer,
                                        simple_targets_file,
                                        constraints):
    set_config('scheduler.check_file', False)
    scheduler = Scheduler(observer,
                          targets_file=simple_targets_file,
                          constraints=constraints)
    # Check the hidden property as the public one
    # will populate if not found.
    assert len(scheduler._observations)


def test_loading_target_file_check_file(observer,
                                        simple_targets_file,
                                        constraints):
    set_config('scheduler.check_file', True)
    scheduler = Scheduler(observer,
                          targets_file=simple_targets_file,
                          constraints=constraints,
                          )
    # Check the hidden property as the public one
    # will populate if not found.
    assert len(scheduler._observations) > 0


def test_loading_target_file_via_property(simple_targets_file,
                                          observer,
                                          constraints):
    scheduler = Scheduler(observer, targets_file=simple_targets_file,
                          constraints=constraints)
    scheduler._observations = dict()
    assert scheduler.observations is not None


def test_with_location(scheduler):
    assert isinstance(scheduler, Scheduler)


def test_loading_bad_target_file(observer):
    with pytest.raises(FileNotFoundError):
        Scheduler(observer, targets_file='/var/path/foo.bar')


def test_new_targets_file(scheduler, simple_targets_file):
    scheduler.targets_file = simple_targets_file
    assert scheduler.observations is not None


def test_new_targets_list(scheduler):
    assert len(scheduler.observations.keys()) > 2
    scheduler.targets_list = [
        {'name': 'Wasp 33',
         'position': '02h26m51.0582s +37d33m01.733s',
         'priority': '100',
         },
        {'name': 'Wasp 37',
         'position': '02h26m51.0582s +37d33m01.733s',
         'priority': '50',
         },
    ]
    assert scheduler.observations is not None
    assert len(scheduler.observations.keys()) == 2


def test_scheduler_add_field(scheduler):
    orig_length = len(scheduler.observations)

    scheduler.add_observation({
        'name': 'Degree Field',
        'position': '12h30m01s +08d08m08s',
    })

    assert len(scheduler.observations) == orig_length + 1


def test_scheduler_add_bad_field(scheduler):
    orig_length = len(scheduler.observations)
    with pytest.raises(error.InvalidObservation):
        scheduler.add_observation({
            'name': 'Duplicate Field',
            'position': '12h30m01s +08d08m08s',
            'exptime': -10
        })

    assert orig_length == len(scheduler.observations)


def test_scheduler_add_duplicate_field(scheduler):
    scheduler.add_observation({
        'name': 'Duplicate Field',
        'position': '12h30m01s +08d08m08s',
        'priority': 100
    })

    assert scheduler.observations['Duplicate Field'].priority == 100

    scheduler.add_observation({
        'name': 'Duplicate Field',
        'position': '12h30m01s +08d08m08s',
        'priority': 500
    })

    assert scheduler.observations['Duplicate Field'].priority == 500


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


def test_scheduler_add_with_exptime(scheduler):
    orig_length = len(scheduler.observations)

    scheduler.add_observation({
        'name': 'Added Field',
        'position': '12h30m01s +08d08m08s',
        'exptime': '60'
    })

    assert len(scheduler.observations) == orig_length + 1
    assert scheduler.observations['Added Field'].exptime == 60 * u.second


def test_remove_field(scheduler):
    orig_keys = list(scheduler.observations.keys())

    # First remove a non-existing field, which should do nothing
    scheduler.remove_observation('123456789')
    assert orig_keys == list(scheduler.observations.keys())

    scheduler.remove_observation('HD 189733')
    assert orig_keys != list(scheduler.observations.keys())
