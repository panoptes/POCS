import pytest

from astropy import units as u

from pocs.utils.config import load_config


@pytest.fixture
def conf():
    return load_config()


def test_location_latitude(conf):
    lat = conf['location']['latitude']
    assert lat >= -90 * u.degree and lat <= 90 * u.degree


def test_location_longitude(conf):
    lat = conf['location']['longitude']
    assert lat >= -360 * u.degree and lat <= 360 * u.degree


def test_location_positive_elevation(conf):
    elev = conf['location']['elevation']
    assert elev >= 0.0 * u.meter
