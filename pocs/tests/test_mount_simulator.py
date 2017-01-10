import os
import pytest

from astropy import units as u
from astropy.coordinates import EarthLocation
from astropy.coordinates import SkyCoord

from pocs.mount.simulator import Mount


def test_no_location():
    with pytest.raises(TypeError):
        Mount()


@pytest.fixture
def mount(config):
    loc = config['location']
    location = EarthLocation(lon=loc['longitude'], lat=loc['latitude'], height=loc['elevation'])
    return Mount(location=location)


def test_connect(mount):
    assert mount.connect() is True


def test_initialize(mount):
    assert mount.initialize() is True


def test_target_coords(mount):
    c = SkyCoord('20h00m43.7135s +22d42m39.0645s')

    mount.set_target_coordinates(c)

    assert mount.get_target_coordinates().to_string() == '300.182 22.7109'


def test_set_park_coords(mount):
    assert mount._park_coordinates is None

    os.environ['POCSTIME'] = '2016-08-13 23:03:01'
    mount.set_park_coordinates()
    assert mount._park_coordinates is not None

    assert mount._park_coordinates.dec.value == -10.0
    assert mount._park_coordinates.ra.value - 322.98 <= 1.0

    os.environ['POCSTIME'] = '2016-08-13 13:03:01'
    mount.set_park_coordinates()

    assert mount._park_coordinates.dec.value == -10.0
    assert mount._park_coordinates.ra.value - 172.57 <= 1.0


def test_status(mount):
    status1 = mount.status()
    assert 'mount_target_ra' not in status1

    c = SkyCoord('20h00m43.7135s +22d42m39.0645s')

    mount.set_target_coordinates(c)

    assert mount.get_target_coordinates().to_string() == '300.182 22.7109'

    status2 = mount.status()
    assert 'mount_target_ra' in status2


def test_update_location_no_init(mount, config):
    loc = config['location']

    location2 = EarthLocation(lon=loc['longitude'], lat=loc['latitude'], height=loc['elevation'] - 1000 * u.meter)

    with pytest.raises(AssertionError):
        mount.location = location2


def test_update_location(mount, config):
    loc = config['location']

    mount.initialize()

    location1 = mount.location
    location2 = EarthLocation(lon=loc['longitude'], lat=loc['latitude'], height=loc['elevation'] - 1000 * u.meter)
    mount.location = location2

    assert location1 != location2
    assert mount.location == location2
