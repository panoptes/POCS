import pytest

import astropy.units as u

from ...mount.ioptron import Mount
from ...utils.config import load_config

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
