import pytest

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
