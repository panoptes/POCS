import pytest

from pocs.mount import create_mount_from_config
from pocs.utils.location import create_location_from_config


def test_bad_mount_port(config):
    conf = config.copy()
    conf['mount']['serial']['port'] = '/dev/'
    site_details = create_location_from_config(conf)
    with pytest.raises(SystemExit):
        create_mount_from_config(config=conf, earth_location=site_details['earth_location'])


@pytest.mark.without_mount
def test_bad_mount_driver(config):
    conf = config.copy()
    conf['mount']['driver'] = 'foobar'
    site_details = create_location_from_config(conf)
    with pytest.raises(SystemExit):
        create_mount_from_config(config=conf, earth_location=site_details['earth_location'])


def test_no_earth_location(config):
    conf = config.copy()
    assert create_mount_from_config(conf, earth_location=None) is None


def test_no_mount_in_config(config):
    conf = config.copy()
    del conf['mount']
    site_details = create_location_from_config(conf)
    assert create_mount_from_config(conf, earth_location=site_details['earth_location']) is None
