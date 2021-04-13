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
def simple_fields_file():
    return get_config('directories.fields') + '/simulator.yaml'


@pytest.fixture
def observer():
    loc = get_config('location')
    location = EarthLocation(lon=loc['longitude'], lat=loc['latitude'], height=loc['elevation'])
    return Observer(location=location, name="Test Observer", timezone=loc['timezone'])


@pytest.fixture()
def fields_list():
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
def scheduler(fields_list, observer, constraints):
    return Scheduler(observer,
                     fields_list=fields_list,
                     constraints=constraints)


def test_scheduler_load_no_params():
    with pytest.raises(TypeError):
        Scheduler()


def test_no_observer(simple_fields_file):
    with pytest.raises(TypeError):
        Scheduler(fields_file=simple_fields_file)


def test_bad_observer(simple_fields_file, constraints):
    with pytest.raises(TypeError):
        Scheduler(fields_file=simple_fields_file,
                  constraints=constraints)


def test_loading_target_file_check_file(observer,
                                        simple_fields_file,
                                        constraints):
    set_config('scheduler.check_file', True)
    scheduler = Scheduler(observer,
                          fields_file=simple_fields_file,
                          constraints=constraints,
                          )
    # Check the hidden property as the public one
    # will populate if not found.
    assert len(scheduler._observations) > 0


def test_loading_target_file_via_property(simple_fields_file,
                                          observer,
                                          constraints):
    scheduler = Scheduler(observer, fields_file=simple_fields_file,
                          constraints=constraints)
    scheduler._observations = dict()
    assert scheduler.observations is not None


def test_with_location(scheduler):
    assert isinstance(scheduler, Scheduler)


def test_loading_bad_target_file(observer):
    with pytest.raises(FileNotFoundError):
        Scheduler(observer, fields_file='/var/path/foo.bar')


def test_new_fields_file(scheduler, simple_fields_file):
    scheduler.fields_file = simple_fields_file
    assert scheduler.observations is not None


def test_new_fields_list(scheduler):
    assert len(scheduler.observations.keys()) > 2
    scheduler.fields_list = [
        {"field":
            {'name': 'Wasp 33',
             'position': '02h26m51.0582s +37d33m01.733s'},
         "observation":
            {'priority': '100'},
         },
        {"field":
            {'name': 'Wasp 37',
             'position': '02h26m51.0582s +37d33m01.733s'},
         "observation": {'priority': '50'}}
    ]
    assert scheduler.observations is not None
    assert len(scheduler.observations.keys()) == 2


def test_scheduler_add_field(scheduler):
    orig_length = len(scheduler.observations)

    scheduler.add_observation({
        "field": dict(name="Degree Field", position='12h30m01s +08d08m08s')})

    assert len(scheduler.observations) == orig_length + 1


def test_scheduler_add_bad_field(scheduler):
    orig_length = len(scheduler.observations)
    with pytest.raises(error.InvalidObservation):

        scheduler.add_observation({
            "field": dict(name="Duplicate Field", position='12h30m01s +08d08m08s'),
            "observation": dict(exptime=-10)})

    assert orig_length == len(scheduler.observations)


def test_scheduler_add_duplicate_field(scheduler):

    scheduler.add_observation({
        "field": dict(name="Duplicate Field", position='12h30m01s +08d08m08s'),
        "observation": dict(priority=100)})

    assert scheduler.observations['Duplicate Field'].priority == 100

    scheduler.add_observation({
        "field": dict(name="Duplicate Field", position='12h30m01s +08d08m08s'),
        "observation": dict(priority=500)})

    assert scheduler.observations['Duplicate Field'].priority == 500


def test_scheduler_add_duplicate_field_different_name(scheduler):
    orig_length = len(scheduler.observations)

    scheduler.add_observation({
        "field": dict(name="Duplicate Field", position='12h30m01s +08d08m08s')})

    scheduler.add_observation({
        "field": dict(name="Duplicate Field 2", position='12h30m01s +08d08m08s')})

    assert len(scheduler.observations) == orig_length + 2


def test_scheduler_add_with_exptime(scheduler):
    orig_length = len(scheduler.observations)

    scheduler.add_observation({
        "field": dict(name="Added Field", position='12h30m01s +08d08m08s'),
        "observation": dict(exptime=60)})

    assert len(scheduler.observations) == orig_length + 1
    assert scheduler.observations['Added Field'].exptime == 60 * u.second


def test_remove_field(scheduler):
    orig_keys = list(scheduler.observations.keys())

    # First remove a non-existing field, which should do nothing
    scheduler.remove_observation('123456789')
    assert orig_keys == list(scheduler.observations.keys())

    scheduler.remove_observation('HD 189733')
    assert orig_keys != list(scheduler.observations.keys())


def test_new_field_custom_type(scheduler):

    field_type = "panoptes.pocs.scheduler.field.Field"
    obs_type = "panoptes.pocs.scheduler.observation.base.Observation"

    orig_length = len(scheduler.observations)

    obs_config = {"field": {'name': 'Custom type',
                            'position': '02h26m51.0582s +37d33m01.733s',
                            'type': field_type},
                  "observation": {'priority': '100',
                                  'type': obs_type}}

    scheduler.add_observation(obs_config)
    assert len(scheduler.observations) == orig_length + 1


def test_new_field_custom_type_bad(scheduler):

    field_type = "panoptes.pocs.scheduler.field.FakeFieldClass"

    obs_config = {"field": {'name': 'Bad custom type',
                            'position': '02h26m51.0582s +37d33m01.733s',
                            'type': field_type},
                  "observation": {'priority': '100'}}

    with pytest.raises(error.InvalidObservation):
        scheduler.add_observation(obs_config)
