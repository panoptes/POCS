import pytest

import astropy.units as u

from ..mount.ioptron import Mount
from ..utils.config import load_config

config = load_config()

mount = None

def test_loading_without_config():
    """ Tests the basic loading of a mount """
    with pytest.raises(AssertionError):
        mount = Mount()

def test_default_config():
    """ Tests the basic loading of a mount """
    mount = Mount(config=config)
    assert mount is not None

def test_ha_dec_failure_01():
    """ Tests ha_dec requires commands """
    mount = Mount(config=config)

    with pytest.raises(AssertionError):
        mount.get_coords_for_ha_dec()

def test_ha_dec_failure_02():
    mount = Mount(config=config)

    with pytest.raises(AssertionError):
        mount.get_coords_for_ha_dec(ha=-170 * u.degree)

def test_ha_dec_failure_03():
    mount = Mount(config=config)

    with pytest.raises(AssertionError):
        mount.get_coords_for_ha_dec(dec=-10 * u.degree)

def test_ha_dec_failure_04():
    mount = Mount(config=config)

    with pytest.raises(AssertionError):
        mount.get_coords_for_ha_dec(ha=-170, dec=-10 * u.degree)
