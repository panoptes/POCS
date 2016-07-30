import pytest

from pocs.mount.ioptron import Mount
from pocs.utils.config import load_config

config = load_config()

mount = None


def test_loading_without_config():
    """ Tests the basic loading of a mount """
    with pytest.raises(TypeError):
        mount = Mount()


def test_default_config():
    """ Tests the basic loading of a mount """
    mount_config = config['mount']
    location = config['location']

    mount = Mount(mount_config, location)
    assert mount is not None
