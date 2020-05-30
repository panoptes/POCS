import pytest

from astroplan import Observer
from astropy import units as u
from astropy.coordinates import EarthLocation
from astropy.coordinates import get_moon
from astropy.time import Time

from collections import OrderedDict

from panoptes.pocs.scheduler.field import Field
from panoptes.pocs.scheduler.observation import Observation

from panoptes.pocs.scheduler.constraint import Altitude
from panoptes.pocs.scheduler.constraint import BaseConstraint
from panoptes.pocs.scheduler.constraint import Duration
from panoptes.pocs.scheduler.constraint import MoonAvoidance
from panoptes.pocs.scheduler.constraint import AlreadyVisited

from panoptes.utils.config.client import get_config
from panoptes.utils import horizon as horizon_utils
from panoptes.utils.serializers import from_yaml


@pytest.fixture(scope='function')
def observer(dynamic_config_server, config_port):
    loc = get_config('location', port=config_port)
    location = EarthLocation(lon=loc['longitude'], lat=loc['latitude'], height=loc['elevation'])
    return Observer(location=location, name="Test Observer", timezone=loc['timezone'])


@pytest.fixture(scope='function')
def horizon_line(dynamic_config_server, config_port):
    obstruction_list = get_config('location.obstructions', default=list(), port=config_port)
    default_horizon = get_config('location.horizon', port=config_port)

    horizon_line = horizon_utils.Horizon(
        obstructions=obstruction_list,
        default_horizon=default_horizon
    )
    return horizon_line


@pytest.fixture(scope='module')
def field_list():
    return from_yaml("""
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
-
    name: M44
    position: 08h40m24s +19d40m00.12s
    priority: 50
""")


@pytest.fixture(scope='module')
def field():
    return Field('Test Observation', '20h00m43.7135s +22d42m39.0645s')


@pytest.fixture(scope='module')
def observation(field):
    return Observation(field)


def test_bad_str_weight():
    with pytest.raises(AssertionError):
        BaseConstraint("1.0")


def test_negative_weight():
    with pytest.raises(AssertionError):
        BaseConstraint(-1.0)


def test_default_weight():
    c = BaseConstraint()
    assert c.weight == 1.0


def test_altitude_subclass():
    assert issubclass(Altitude, BaseConstraint)


def test_altitude_no_minimum():
    with pytest.raises(AssertionError):
        Altitude()


def test_altitude_bad_param():
    with pytest.raises(AssertionError):
        Altitude(30)


def test_basic_altitude(observer, field_list, horizon_line):

    # Target is at ~34 degrees altitude and 79 degrees azimuth
    time = Time('2018-01-19 07:10:00')
    m44 = field_list[-1]

    # First check out with default horizon
    ac = Altitude(horizon_line)
    observation = Observation(Field(**m44), **m44)
    veto, score = ac.get_score(time, observer, observation)

    assert veto is False


def test_custom_altitude(observer, field_list, horizon_line):
    time = Time('2018-01-19 07:10:00')
    m44 = field_list[-1]

    # Then check veto with block
    horizon_line = horizon_utils.Horizon(
        obstructions=[
            [[40, 70], [40, 80]]
        ],
    )
    ac = Altitude(horizon_line)
    observation = Observation(Field(**m44), **m44)
    veto, score = ac.get_score(time, observer, observation)

    assert veto is True


def test_big_wall(observer, field_list):
    time = Time('2018-01-19 07:10:00')
    horizon_line = horizon_utils.Horizon(
        obstructions=[
            [[90, 0], [90, 359]]
        ],
    )

    vetoes = list()
    for field in field_list:
        observation = Observation(Field(**field), **field)

        ac = Altitude(horizon_line)
        veto, score = ac.get_score(time, observer, observation)
        vetoes.append(veto)

    assert all(vetoes)


def test_duration_veto(observer, field_list):
    dc = Duration(30 * u.degree)

    time = Time('2016-08-13 17:42:00.034059')
    sunrise = observer.tonight(time=time, horizon=18 * u.degree)[-1]

    hd189733 = field_list[0]
    observation = Observation(Field(**hd189733), **hd189733)
    veto, score = dc.get_score(time, observer, observation, sunrise=sunrise)
    assert veto is True

    wasp33 = field_list[-3]
    observation = Observation(Field(**wasp33), **wasp33)
    veto, score = dc.get_score(time, observer, observation, sunrise=sunrise)
    assert veto is False


def test_duration_score(observer):
    dc = Duration(30 * u.degree)

    time = Time('2016-08-13 10:00:00')
    sunrise = observer.tonight(time=time, horizon=18 * u.degree)[-1]

    observation1 = Observation(Field('HD189733', '20h00m43.7135s +22d42m39.0645s'))  # HD189733
    observation2 = Observation(Field('Hat-P-16', '00h38m17.59s +42d27m47.2s'))  # Hat-P-16

    veto1, score1 = dc.get_score(time, observer, observation1, sunrise=sunrise)
    veto2, score2 = dc.get_score(time, observer, observation2, sunrise=sunrise)

    assert veto1 is False and veto2 is False
    assert score2 > score1


def test_moon_veto(observer):
    mac = MoonAvoidance()

    time = Time('2016-08-13 10:00:00')

    moon = get_moon(time, observer.location)

    observation1 = Observation(Field('Sabik', '17h10m23s -15d43m30s'))  # Sabik

    veto1, score1 = mac.get_score(time, observer, observation1, moon=moon)

    assert veto1 is True


def test_moon_avoidance(observer):
    mac = MoonAvoidance()

    time = Time('2016-08-13 10:00:00')

    moon = get_moon(time, observer.location)

    observation1 = Observation(Field('HD189733', '20h00m43.7135s +22d42m39.0645s'))  # HD189733
    observation2 = Observation(Field('Hat-P-16', '00h38m17.59s +42d27m47.2s'))  # Hat-P-16

    veto1, score1 = mac.get_score(time, observer, observation1, moon=moon)
    veto2, score2 = mac.get_score(time, observer, observation2, moon=moon)

    assert veto1 is False and veto2 is False
    assert score2 > score1


def test_already_visited(observer):
    avc = AlreadyVisited()

    time = Time('2016-08-13 10:00:00')

    # HD189733
    observation1 = Observation(Field('HD189733', '20h00m43.7135s +22d42m39.0645s'))
    # Hat-P-16
    observation2 = Observation(Field('Hat-P-16', '00h38m17.59s +42d27m47.2s'))
    # Sabik
    observation3 = Observation(Field('Sabik', '17h10m23s -15d43m30s'))

    observed_list = OrderedDict()

    observation1.seq_time = '01:00'
    observation2.seq_time = '02:00'
    observation3.seq_time = '03:00'

    observed_list[observation1.seq_time] = observation1
    observed_list[observation2.seq_time] = observation2

    veto1, score1 = avc.get_score(time, observer, observation1, observed_list=observed_list)
    veto2, score2 = avc.get_score(time, observer, observation3, observed_list=observed_list)

    assert veto1 is True
    assert veto2 is False
