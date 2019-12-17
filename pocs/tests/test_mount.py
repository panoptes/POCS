import pytest

from pocs.mount import create_mount_from_config, AbstractMount
from pocs.utils.error import MountNotFound
from pocs.utils.location import create_location_from_config


@pytest.fixture
def conf_with_mount(config_with_simulated_mount):
    return config_with_simulated_mount.copy()


def test_mount_not_in_config(config):
    conf = config.copy()

    # Remove mount info
    del conf['mount']

    with pytest.raises(MountNotFound):
        create_mount_from_config(conf)


@pytest.mark.without_mount
def test_mount_no_config_param():
    # Will fail because it's not a simulator and no real mount attached
    with pytest.raises(MountNotFound):
        create_mount_from_config()


def test_bad_mount_port(config):
    conf = config.copy()
    conf['mount']['serial']['port'] = 'foobar'
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


def test_create_mount_with_earth_location(conf_with_mount):
    site_details = create_location_from_config(conf_with_mount)
    earth_location = site_details['earth_location']
    assert isinstance(create_mount_from_config(
        conf_with_mount, earth_location=earth_location), AbstractMount) is True


def test_create_mount_without_earth_location(conf_with_mount):
    assert isinstance(create_mount_from_config(
        conf_with_mount, earth_location=None), AbstractMount) is True
