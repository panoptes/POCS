import pytest

from pocs_alerter.horizon.horizon_range import Horizon
from astroplan import Observer
import numpy as np
from astropy import units as u

@pytest.fixture
def observer():

    lat = np.power(-1, np.random.randint(2)) * np.random.random() * 90 * u.deg
    lon = np.power(-1, np.random.randint(2)) * np.random.random() * 180 * u.deg
    elevation = np.random.random() * 1500.0 * u.m

    name = 'sample location'

    observer = Observer(latitude = lat, longitude = lon, elevation = elevation, name = name)

    return observer

@pytest.fixture
def altitude():
    alt = np.random.random(1) * 80.0 * u.deg
    return alt

def test_modulus_ra(observer, altitude):

    horizon = Horizon(observer, altitude)

    min_val = 0.0
    max_val = 360.0

    val = 395.25

    val = horizon.modulus(val, min_val, max_val)

    assert (val <= max_val) and (val >= min_val)


def test_modulus_dec(observer, altitude):

    horizon = Horizon(observer, altitude)

    min_val = -90.0
    max_val = 90.0

    val = -115.0

    val = horizon.modulus(val, min_val, max_val)

    assert (val <= max_val) and (val >= min_val)

def test_zenith(observer, altitude):

    horizon = Horizon(observer, altitude)

    zenith = horizon.zenith_ra_dec()

    assert zenith['ra'].value <= 360.0 and zenith['ra'].value >= 0.0
    assert zenith['dec'].value <= 90.0 and zenith['dec'].value >= -90.0