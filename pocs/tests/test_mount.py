import pytest

from pocs.mount import create_mount_from_config, AbstractMount
from pocs.utils.error import MountNotFound
from pocs.utils.location import create_location_from_config


def test_bad_mount_port(config):
    conf = config.copy()
    conf['mount']['serial']['port'] = '/dev/'
    with pytest.raises(MountNotFound):
        create_mount_from_config(conf)


@pytest.mark.without_mount
def test_bad_mount_driver(config):
    conf = config.copy()
    conf['mount']['driver'] = 'foobar'
    with pytest.raises(MountNotFound):
        create_mount_from_config(conf)
    conf['mount']['driver'] = 1234
    with pytest.raises(MountNotFound):
        create_mount_from_config(conf)


def test_create_mount_with_earth_location(config):
    conf = config.copy()
    site_details = create_location_from_config(conf)
    earth_location = site_details['earth_location']
    assert isinstance(create_mount_from_config(conf, earth_location=earth_location), AbstractMount) is True


def test_create_mount_without_earth_location(config):
    conf = config.copy()
    assert isinstance(create_mount_from_config(conf, earth_location=None), AbstractMount) is True
