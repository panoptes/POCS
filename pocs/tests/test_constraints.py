import pytest
import yaml

from astropy import units as u
from astropy.coordinates import EarthLocation
from astropy.coordinates import get_moon
from astropy.time import Time


from astroplan import Observer

from pocs.scheduler.field import Field
from pocs.scheduler.observation import Observation
from pocs.utils.config import load_config

from pocs.scheduler.constraint import Altitude
from pocs.scheduler.constraint import BaseConstraint
from pocs.scheduler.constraint import Duration
from pocs.scheduler.constraint import MoonAvoidance


config = load_config()

loc = config['location']
location = EarthLocation(lon=loc['longitude'], lat=loc['latitude'], height=loc['elevation'])
observer = Observer(location=location, name="Test Observer", timezone=loc['timezone'])
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


@pytest.fixture
def field():
    return Field('Test Observation', '20h00m43.7135s +22d42m39.0645s')


@pytest.fixture
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
    with pytest.raises(TypeError):
        Altitude()


def test_altitude_minimum_no_units():
    with pytest.raises(TypeError):
        Altitude(30)


def test_altitude_vals():
    ac = Altitude(minimum=30 * u.degree)
    assert ac.minimum == 30 * u.degree


def test_altitude_defaults():
    ac = Altitude(18 * u.degree)
    assert ac.weight == 1.0
    assert ac.minimum == 18 * u.degree


def test_altitude_vetor_for_up_target(observation):
    ac = Altitude(18 * u.degree)

    time = Time('2016-08-13 07:42:00.034059')

    veto, score = ac.get_score(time, observer, observation)

    assert veto is False


def test_altitude_veto_for_down_target(observation):
    ac = Altitude(18 * u.degree)

    time = Time('2016-08-13 17:42:00.034059')

    veto, score = ac.get_score(time, observer, observation)

    assert veto is True


def test_duration_veto():
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


def test_duration_score():
    dc = Duration(30 * u.degree)

    time = Time('2016-08-13 10:00:00')
    sunrise = observer.tonight(time=time, horizon=18 * u.degree)[-1]

    observation1 = Observation(Field('HD189733', '20h00m43.7135s +22d42m39.0645s'))  # HD189733
    observation2 = Observation(Field('Hat-P-16', '00h38m17.59s +42d27m47.2s'))  # Hat-P-16

    veto1, score1 = dc.get_score(time, observer, observation1, sunrise=sunrise)
    veto2, score2 = dc.get_score(time, observer, observation2, sunrise=sunrise)

    assert veto1 is False and veto2 is False
    assert score2 > score1


def test_moon_veto():
    mac = MoonAvoidance()

    time = Time('2016-08-13 10:00:00')

    moon = get_moon(time, observer.location)

    observation1 = Observation(Field('Sabik', '17h10m23s -15d43m30s'))  # Sabik

    veto1, score1 = mac.get_score(time, observer, observation1, moon=moon)

    assert veto1 is True


def test_moon_avoidance():
    mac = MoonAvoidance()

    time = Time('2016-08-13 10:00:00')

    moon = get_moon(time, observer.location)

    observation1 = Observation(Field('HD189733', '20h00m43.7135s +22d42m39.0645s'))  # HD189733
    observation2 = Observation(Field('Hat-P-16', '00h38m17.59s +42d27m47.2s'))  # Hat-P-16

    veto1, score1 = mac.get_score(time, observer, observation1, moon=moon)
    veto2, score2 = mac.get_score(time, observer, observation2, moon=moon)

    assert veto1 is False and veto2 is False
    assert score2 > score1
